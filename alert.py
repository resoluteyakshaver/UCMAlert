import paramiko
import time
import re
from paramiko_expect import SSHClientInteraction
import requests
import csv
import concurrent.futures
import os
import socket

'''
Messaging application to send notifications to all available devices (registered) in the event of an emergency.
Author: Christian Thorsnes
Version:
		20 Jan 2020 - 0.1.0 - Many optimizations (Alert time just over a minute)
		19 Jan 2020 - 0.0.2 - New Ring
		08 Jan 2020 - 0.0.1 - Quick Release
'''

def dispatch_msg(ip=None, msg=None):
    //Change incoming.raw with whatever phone alert sound has been uploaded to CUCM
    xml2 = '''XML=<CiscoIPPhoneExecute><ExecuteItem Priority="1" URL="Play:incoming.raw"/></CiscoIPPhoneExecute>'''
    xml1 = '''XML=<CiscoIPPhoneText><Prompt>EMERGENCY ALERT</Prompt><Text>'''+ msg + '''</Text></CiscoIPPhoneText>'''
    headers = {'authorization': 'Basic c2VuZG1zZzpzZW5kbXNn','content-type': 'application/xml'}
    #headers = {'authorization': 'Basic test','content-type': 'application/xml'} #Uncomment to fail-auth and launch test
    #cleaned = re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",ip)
    #print(cleaned)
    phone = 'http://' + ip.strip() + '/CGI/Execute'
    try:
        requests.post(phone, data=xml1, headers=headers).text
    except requests.exceptions.ReadTimeout:
        pass
    except socket.timeout:
        pass
    except requests.exceptions.ConnectTimeout:
        pass
    try:
        requests.post(phone, data=xml2, headers=headers, timeout=0.750).text
    except requests.exceptions.ReadTimeout:
        pass
    except socket.timeout:
        pass
    except requests.exceptions.ConnectTimeout:
        pass

def GetRegisteredPhones(cucm = None, clusterpass = None):
    hostAddress = cucm
    u = 'admin'
    p = clusterpass

    output = ''
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=hostAddress, username=u, password=p, timeout=25, banner_timeout=120)
    prompt = 'admin:'
    interact = SSHClientInteraction(client, timeout=30, display=False)
    try:
        interact.expect(prompt, timeout=15)
    except:
        interact.send('\n')
        interact.expect(prompt)
    trash = interact.current_output_clean
    try:
        interact.send('show risdb query phone')
        interact.expect(prompt, timeout=15)
    except:
        interact.send('\n')
        interact.expect(prompt)
    output = interact.current_output_clean
    regex = r"(DeviceName[\s\S]*)\n\n"
    matches = re.findall(regex, output, re.DOTALL)
    client.close()
    f = open("phones.csv","a+", encoding="utf-8")
    for match in matches:
        f.write(match)
    f.close()

def AlertInput(collected_input = None):
    print('Emergency Alert to be sent: ')
    print('(1) Critical Alert: Seek Shelter Immediately!')
    print('(2) Test Alert Please Ignore')
    print('(3) Configurable Alert Message')
    collected_input = input()
    if collected_input == '1':
        return 'Critical Alert, Seek Shelter Immediately! This is not a test!'
    if collected_input == '2':
        return 'Test Message for the Emergency Alerting System'
    if collected_input == '3':
        inp = input()
        return inp
    else:
        print('Invalid Entry')
        alert = None
        return 0

print('Enter Cluster Password: ')
cucm_passwd = input()
alert = ""
while True:
    alert = AlertInput()
    if alert:
        break

print(alert)

//Populate this string list with IPs of CUCMs
CLUSTER = ['','']


for CUCM in CLUSTER:
    if os.path.exists('phones.csv'):
        print("Deleting old raw entry file...")
        os.remove('phones.csv')

if os.path.exists('first_edit.csv'):
    print("Deleting old cleaned registrations file...")
    os.remove('first_edit.csv')

with concurrent.futures.ThreadPoolExecutor(len(CLUSTER)) as executor:
    future_data = {executor.submit(GetRegisteredPhones, CUCM, cucm_passwd): CUCM for CUCM in CLUSTER}
    for future in concurrent.futures.as_completed(future_data):
        data = future_data[future]
        try:
            data = future.result()
        except Exception as exc:
            print('%r generated an exception: %s' % (data, exc))
        print("Iterating next step...")
for CUCM in CLUSTER:
    with open('phones.csv', 'r', encoding="utf-8") as inp, open('first_edit.csv', 'w', encoding="utf-8") as out:
        writer = csv.writer(out)
        for row in csv.reader(inp):
            if (row[7] != " unr") and (row[7] != " rej"):
                writer.writerow(row)

with open('first_edit.csv', 'r', encoding="utf-8") as infile:
  # read the file as a dictionary for each row ({header : value})
  reader = csv.DictReader(infile)
  data = {}
  for row in reader:
    for header, value in row.items():
      try:
        data[header].append(value)
      except KeyError:
        data[header] = [value]

ips = data[' Ipaddr']
print("Sending Message to all active devices...")

with concurrent.futures.ThreadPoolExecutor(max_workers=64) as executor:
    future_data = {executor.submit(dispatch_msg, ip, alert): ip for ip in ips}
    for future in concurrent.futures.as_completed(future_data):
        data = future_data[future]
        try:
            data = future.result()
        except Exception as exc:
            print('%r generated an exception: %s' % (data, exc))
        print('Thread complete.')

print("Execution complete.")

