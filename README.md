# restore_net_use
Restores Windows net drives on system boot.

## The problem
The problem with Windows 7 and above is that named network connections, e.g., `S:` are not automatically restored when booting up - the drive icon remain crossed out and the drive inaccessible.

Instead the user must manually fire up Windows Explorer and click on the drive to restore the connection. For the most part this is sufficient, but when using a PC for some automated tasks, it means that after a reboot some manual action can be performed.

## The solution
This Python script is intended to solve the problem. It runs the `NET USE` command, parses the output and tries to restore each connection.

It can optionally log progress to a log file and send mail. If the network interface is slow to come up, the script can first check network connectivity by attempting to contact an arbitrary server (the Google's public DNS server by default).

## Usage
The script requires Python (tested with 2.7.15). Alternatively you can package it with, e.g., [PyInstaller](https://www.pyinstaller.org/) and run it as a standalone executable.

Use Windows Task Scheduler to schedule a script to run at boot. The script's parameters can be read from a file, making it easy to tweak them. Add a task and:
- On the *General* tab set it to run whether the user is logged on or not and with the highest priviliges
- On the *Trigger* tab add a trigger *At Startup*
- On the *Actions* tab add action *Start a program* with:
  - *Program/script* containing `<PATH_TO_PYTHON>\python.exe` and
  - *Add arguments (optional)* containing `<PATH_TO_SCRIPT>\restore_net_use.py @<PATH_TO_OPTIONS_FILE>\restore_net_use.opt`

Here is an example of an options file, `restore_net_use.opt` used on the author's system
```
--conntimeout
600
--logfile
d:\temp\restore_net_use.log
--smtp
mail.zag.si
--recipient
jan.kalin@zag.si
```
