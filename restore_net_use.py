#!/usr/bin/env python

"""restore_net_use.py: Restores Windows net drives on system boot"""

__author__ = "Jan Kalin"
__credits__ = ["Jan Kalin"]
__license__ = "MIT"
__maintainer__ = "Jan Kalin"
__email__ = "jan.kalin@zag.si"
__status__ = "Development"

###########################################################################

import argparse
import datetime
from email import utils
import os
import re
import smtplib
import socket
import subprocess
import sys
import time

###########################################################################

description = """Tries to restore net drives at startup.

Calls Windows command 'NET USE' and parses the connections remembered by the
system. It the tries to restore each connection.

Can optionally send mail and write to log file."""

parser = argparse.ArgumentParser(description=description,
                               fromfile_prefix_chars='@', 
                               formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--timeout", help="Timeout in seconds for each NET USE operation", type=int, default=60)
parser.add_argument("--conntest", help="Try connecting to ADDR:PORT as a test of general connectivity. The default is Google's public DNS server", nargs=2, default=['8.8.8.8', 53])
parser.add_argument("--conntimeout", help="Timeout for connectivity test. Do not test if undefined", type=int)
parser.add_argument("--logfile", help="Write messages to this log file. Do not write if undefined")
parser.add_argument("--smtp", help="SMTP server for sending messages. Do not send messages if undefined")
parser.add_argument("--sender", help="Sender email address for sending messages", default="{}@{}".format(os.path.basename(sys.argv[0]), socket.getfqdn()))
parser.add_argument("--recipients", help="Recipient email addresses for sending messages", nargs='+')
parser.add_argument("--testmail", help="Log and send a test message", action='store_true')
parser.add_argument("--onebyone", help="Restore connections one by one for debugging purposes", action='store_true')

args = parser.parse_args()

###########################################################################
# %%

def conntest(addr_port, timeout):
    start = datetime.datetime.now()
    while True:
        try:
            socket.create_connection((addr_port[0], int(addr_port[1])), 5)
            return True
        except Exception:
            time.sleep(1)
            if datetime.datetime.now() > start + datetime.timedelta(seconds=timeout):
                return False


def log(logfile, lines):
    if not logfile or not lines:
        return
    if type(lines) == str:
        lines = [lines]
    try:
        with file(logfile, 'a') as f:
            for line in lines:
                f.write("{}\t{}\n".format(datetime.datetime.now(), line))
    except Exception:
        pass


def send(logfile, smtp, sender, recipients, lines):
    if not smtp or not sender or not recipients or not lines:
        return
    if type(lines) == str:
        lines = [lines]
    try:
        mess = ["Date: {}".format(utils.formatdate(time.mktime(time.localtime()), True)),
                "From: {}".format(sender),
                "To: {}".format(", ".join(recipients)),
                "Subject: NET restore report",
                "",
                "\n".join(lines)]
        s = smtplib.SMTP(smtp)
        s.sendmail(sender, recipients, "\n".join(mess))
        s.quit()
    except Exception:
        log(logfile, "SMTP server {} unreachable/unusable".format(smtp))
   

def log_and_send(logfile, smtp, sender, recipients, lines):
    log(logfile, lines)
    send(logfile, smtp, sender, recipients, lines)

def list_connections(timeout):
    while True:
        start = datetime.datetime.now()
        try:
            net_use = subprocess.check_output("net use".split())
            errors = False
            break
        except Exception:
            errors = True
            if datetime.datetime.now() > start + datetime.timedelta(seconds=timeout):
                break
            else:
                time.sleep(1)
    return (errors, None if errors else parse_connections(net_use))
    

def parse_connections(line):
    lines = line.splitlines()
    connections = []
    for line, next in zip(lines[:-1], lines[1:]):
        cols = line.split()
        nextcols = next.split()
        if len(cols) == 6 and re.match("[A-Z]:", cols[1]) and cols[3:] == ['Microsoft', 'Windows', 'Network'] or\
            len(cols) == 3 and len(nextcols) == 3 and re.match("[A-Z]:", cols[1]) and nextcols == ['Microsoft', 'Windows', 'Network']:
            connections.append((cols[0] == 'ON', cols[1], cols[2]))
    return connections


def connect(connection, timeout):
    start = datetime.datetime.now()
    while True:
        try:
            subprocess.check_output("net use {} {}".format(connection[1], connection[2]).split(), stderr=subprocess.STDOUT)
            errors = False
            break
        except Exception as e:
            errors = True
            if datetime.datetime.now() > start + datetime.timedelta(seconds=timeout):
                break
            else:
                time.sleep(1)
    return not errors

###########################################################################
# %%

## Perhaps just send a test mail
if args.testmail:
    log_and_send(args.logfile, args.smtp, args.sender, args.recipients, "This is a test message")
    sys.exit(0)

## Perhaps test connectivity
if args.conntimeout and not conntest(args.conntest, args.conntimeout):
    log_and_send(args.logfile, args.smtp, args.sender, args.recipients, "{}:{} not reachable after {}s".format(args.conntest[0], args.conntest[1], args.conntimeout))
    sys.exit(1)

## Get a list of connections
(errors, connections) = list_connections(args.timeout)
if errors:
    log_and_send(args.logfile, args.smtp, args.sender, args.recipients, "Could not read connection list")
    sys.exit(1)

## Restore connections
loglines = []
for idx, connection in enumerate(connections):
    reportline = "{} {}".format(connection[1], connection[2])
    if connection[0]:
        logline = "Existing {}".format(reportline)
    else:
        if (args.onebyone and not idx or not args.onebyone) and connect(connection, args.timeout):
            logline = "Restored {}".format(reportline)
        else:
            logline = "Problems {}".format(reportline)
    log(args.logfile, logline)
    loglines.append(logline)
send(args.logfile, args.smtp, args.sender, args.recipients, loglines)