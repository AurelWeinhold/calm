#Author: Leo Wilhelm Lierse
#calmnetworkconfig.py

#only works on linux with networkd(systemd)
#requires: ip, awk, python3, systemd

import subprocess # to use cli commands
import os
import sys # to use arguments
import argparse

if sys.version_info[0] < 3: # this script only works with python3
    raise Exception("Python 3 or higher is required!")

#build argument parser
parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", help="increases log verbosity", action="store_true")
parser.add_argument("--dontask", help="disable asking for action", action="store_true")
parser.add_argument("--ip", help="specify the static ip for the second interface, defaults to 10.0.45.194/24")
parser.add_argument("gateway", help="specify the gateway for the second interface")
parser.add_argument("--nameserver", help="specify nameservers; use multiple times for multiple nameserver", action="append")
args = parser.parse_args() #parse arguments


if(args.verbose):
    print("starting network configuration...") 
    print("collecting information about interfaces...")

#command to get interfaces and MAC address
cmd_ip_link = ['ip', '-o', 'link'] #get all interface data
cmd_awk = ['awk', '$2 != "lo:" && $2 != "docker:" && $2 !~ /docker.:/ {print $2, $(NF-2)}'] # remove all unneccassary information and filter loopback and docker interfaces
proc_ip_link = subprocess.Popen(cmd_ip_link, stdout=subprocess.PIPE) #pipe output into second command
proc_awk = subprocess.Popen(cmd_awk, stdin=proc_ip_link.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
proc_ip_link.stdout.close() #close first process

o, e = proc_awk.communicate() #get data from second process

if proc_awk.returncode != 0: #Failed to use second command
    print("Error: " + e.decode('ascii'))
    exit(-1)

if(args.verbose):
    print("collected interface data!")
    print("INTERFACES: \n" + o.decode('ascii'))

#split string into array, so that arr[2k] = interface name and arr[2k+1] = interface mac-address
interfaces = o.decode('ascii').strip().split("\n")
interfaceaddr = []
for i in interfaces:
    interfaceaddr.extend(i.split(": "))

if len(interfaceaddr) < 4: #we need minimum 2 interfaces, so 4 entries in the array
    print("not enough interfaces on machine to use calm")
    exit(-1)

#we default to the first two interfaces

#start first two interfaces. this action is idempotent and will not break anything.
cmd_up_interface_one = ['sudo', 'ip', 'link', 'set', interfaceaddr[0], 'up']
cmd_up_interface_two = ['sudo', 'ip', 'link', 'set', interfaceaddr[2], 'up']
proc_up_interface_one = subprocess.Popen(cmd_up_interface_one, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
proc_up_interface_two = subprocess.Popen(cmd_up_interface_two, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

o, e = proc_up_interface_one.communicate() #start first interface

if proc_up_interface_one.returncode != 0: 
    print("Error: " + e.decode('ascii'))
    exit(-1)

o, e = proc_up_interface_two.communicate() #start second interface

if proc_up_interface_two.returncode != 0:
    print("Error: " + e.decode('ascii'))
    exit(-1)

#generate new config file #we just fill the blank config file with the necessary information
if(args.verbose):
    print("generating config file")

#get ip
static_ip = args.ip 
if static_ip == None:
    static_ip = "10.0.45.194/24"

#get gateway
static_gateway = args.gateway

#get nameserver
static_nameserver = ""
if args.nameserver != None:
    static_nameserver += "["
    for ns in args.nameserver:
        static_nameserver += ns + ","
    static_nameserver += "]" 
else:
    static_nameserver = "[8.8.8.8]"

#generate config from blank
configuration = """network:
  version: 2
  renderer: networkd
  ethernets:
    lan:
      match:
        macaddress: %s
      dhcp4: true
      set-name: calm0
    staticlan:
      match:
        macaddress: %s
      set-name: calm1
      addresses: 
        - %s
      gateway4: %s
      nameservers:
        addresses: %s
""" % (interfaceaddr[1], interfaceaddr[3], static_ip, static_gateway, static_nameserver)

if(args.verbose):
    print(configuration)

#check before continueing
if(args.dontask == False):
    inpt = input("enter y to continue writing config: ")
    if inpt != "y":
        exit(-1)

#write to file
if(args.verbose):
    print("writing config into file")

#write to file
f = open("/etc/netplan/z_calm-auto-config.yaml", "w")
f.write(configuration)
f.close()

#test configuration
if(args.verbose):
    print("generating configuration")

cmd_test_netplan_config = ['sudo', 'netplan', '--debug', 'generate']
proc_test_netplan_config = subprocess.Popen(cmd_test_netplan_config, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

o, e = proc_test_netplan_config.communicate()

if(args.verbose):
    print(o.decode('ascii'))

#when generate fails, delete file
if proc_test_netplan_config.returncode != 0:
    print("Error: " + e.decode('ascii'))
    if os.path.exists("/etc/netplan/z_calm-auto-config.yaml"):
        os.remove("/etc/netplan/z_calm-auto-config.yaml")
    exit(-1)

#if the user does not want to continue, delete the file
if(args.dontask == False):
    inpt = input("enter y to continue applying config: ")
    if inpt != "y":
        if os.path.exists("/etc/netplan/z_calm-auto-config.yaml"):
            os.remove("/etc/netplan/z_calm-auto-config.yaml")
        exit(-1)

#apply configuration
print("applying configuration")

cmd_apply_netplan_config = ['sudo', 'netplan', 'apply']
proc_apply_netplan_config = subprocess.Popen(cmd_apply_netplan_config, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

o, e = proc_apply_netplan_config.communicate()

if(args.verbose):
    print(o.decode('ascii'))

#if the apply failed delete the file
if proc_apply_netplan_config.returncode != 0:
    print("Error: " + e.decode('ascii'))
    if os.path.exists("/etc/netplan/z_calm-auto-config.yaml"):
        os.remove("/etc/netplan/z_calm-auto-config.yaml")
    exit(-1)

print("configuration finished")
exit(0)