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
parser.add_argument("--loops", help="Loop this many times od until all connections have been restored. 0 means loop forever", type=int, default=1)
parser.add_argument("--loopdelay", help="Delay in seconds between loops", type=int, default=10)
parser.add_argument("--conntest", help="Try connecting to ADDR:PORT as a test of general connectivity. The default is Google's public DNS server. Port 445 is SMB port", default='8.8.8.8:53', metavar="ADDR:PORT")
parser.add_argument("--conntimeout", help="Timeout for connectivity test. Do not test if undefined", type=int)
parser.add_argument("--logfile", help="Write messages to this log file. Do not write if undefined")
parser.add_argument("--smtp", help="SMTP server for sending messages. Do not send messages if undefined")
parser.add_argument("--sender", help="Sender email address for sending messages", default="{}@{}".format(os.path.basename(sys.argv[0]), socket.getfqdn()))
parser.add_argument("--recipients", help="Recipient email addresses for sending messages", nargs='+')
parser.add_argument("--testmail", help="Log and send a test message", action='store_true')
parser.add_argument("--onebyone", help="Restore connections one by one for debugging purposes", action='store_true')
parser.add_argument("--dumpnetuse", help="Dump NET USE command results to log", action='store_true')

args = parser.parse_args()

## Sanity checks
if args.timeout < 1:
    raise ValueError("Option --timeout must be positive")
if args.loops < 1:
    raise ValueError("Option --loops must be positive")
if args.loopdelay < 1:
    raise ValueError("Option --loopdelay must be positive")
if args.conntimeout and args.conntimeout < 0:
    raise ValueError("Option --conntimeout must be non-negative")

###########################################################################
# %%

def conntest(addr_port, timeout):
    """Test connection"""
    
    start = datetime.datetime.now()
    while True:
        try:
            socket.create_connection((addr_port[0], int(addr_port[1])), 5)
            return True
        except Exception:
            time.sleep(1)
            if datetime.datetime.now() > start + datetime.timedelta(seconds=timeout):
                return False


def log(logfile, lines, loglines=None):
    """Write to logfile and optionally append to an existing list of loglines"""
    
    if not logfile or not lines:
        return
    if type(lines) == str:
        lines = [lines]
    try:
        with file(logfile, 'a') as f:
            for line in lines:
                f.write("{}\t{}\n".format(datetime.datetime.now(), line))
            if loglines:
                loglines.append(line)
    except Exception:
        pass
    if loglines:
        return loglines


def send(logfile, smtp, sender, recipients, lines):
    """Send lines via email"""
    
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
    """Write to log and send email"""
    
    log(logfile, lines)
    send(logfile, smtp, sender, recipients, lines)

def list_connections(timeout, dumpnetuse=False):
    """Call NET USE to determine the state of connections"""
    
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
    return (errors, None if errors else parse_connections(net_use, dumpnetuse))
    

def parse_connections(line, dumpnetuse=False):
    """Parse the output of NET USE"""
    
    lines = line.splitlines()
    if dumpnetuse:
        log(args.logfile, str(lines))
    
    connections = []
    for line, next in zip(lines[:-1], lines[1:]):
        cols = line.split()
        nextcols = next.split()
        if len(cols) == 6 and re.match("[A-Z]:", cols[1]) and cols[3:] == ['Microsoft', 'Windows', 'Network'] or\
            len(cols) == 3 and len(nextcols) == 3 and re.match("[A-Z]:", cols[1]) and nextcols == ['Microsoft', 'Windows', 'Network']:
            connections.append((cols[0] == 'OK', cols[1], cols[2]))
    return connections


def connect(connection, timeout):
    """Tries to reconnect a connection"""
    
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
    if not args.smtp or not args.recipients:
        raise ValueError("Missing option(s) --smtp and/or --recipient")
    log_and_send(args.logfile, args.smtp, args.sender, args.recipients, "This is a test message")
    sys.exit(0)

## Perhaps test connectivity
if args.conntimeout and not conntest(args.conntest.split(':'), args.conntimeout):
    log_and_send(args.logfile, args.smtp, args.sender, args.recipients, "{} not reachable after {}s".format(args.conntest, args.conntimeout))
    sys.exit(1)

## Loop until connections have been restored
loglines = []
for loop in range(args.loops):

    ## Log loop
    loglines = log(args.logfile, "Loop {} of {}".format(loop+1, args.loops if not args.loops == sys.maxint else 'inf'), loglines)
    if loop:
        loglines = log(args.logfile, "Delay {}s".format(args.loopdelay), loglines)
        time.sleep(args.loopdelay)
    
    ## Get a list of connections and we're done if they are all connected
    (errors, connections) = list_connections(args.timeout, args.dumpnetuse)
    if errors:
        log_and_send(args.logfile, args.smtp, args.sender, args.recipients, "Could not read connection list")
        sys.exit(1)
    
    ## Get a list of connected connections
    ok = [x[1]+x[2] for x in connections if x[0]]
    if len(ok):
        loglines = log(args.logfile, "Existing {}".format(", ".join(ok)), loglines)
        if len(ok) == len(connections):
            break
    for idx, connection in enumerate(connections):
        reportline = "{}{}".format(connection[1], connection[2])
        if not connection[0]:
            if (args.onebyone and not idx or not args.onebyone) and connect(connection, args.timeout):
                logline = "Restored {}".format(reportline)
            else:
                logline = "Problems {}".format(reportline)
        loglines = log(args.logfile, logline, loglines)

## Done
send(args.logfile, args.smtp, args.sender, args.recipients, loglines)
