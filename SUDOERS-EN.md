# PSE Riemann — narrow sudoers rule for the SSH guardian (step by step)

The SSH guardian only does **reversible** things on its own: it ends one SSH session, and it **blocks an IP address for 24 h**, after which the block lifts itself. That needs root, but only for **one small program** that validates every argument:

```
/usr/lib/pse-riemann/pse-guard-helper   check | block-ip IP | unblock-ip IP | kill-session PID
```

Without this rule the guardian **never acts silently**: it raises a big red alarm with sound and shows the exact command you can run yourself.

A permanent block and stopping SSH are **never** automatic. They are proposals in "Čeka tvoju odluku", with the exact command.

## What the rule allows (and what it does not)

- Allows: your user may run **only** `pse-guard-helper` without a password.
- The helper refuses loopback (127.x, ::1), 0.0.0.0, broadcast, malformed addresses, and any PID that is not `sshd`.
- The app uses it only if it is **owned by root** and writable by nobody else. A user-writable helper behind sudo would be a root shell, so the app refuses to use one.
- Allows nothing else: no `ufw`, no `systemctl`, no shell.

## Steps

1. **Install the .deb.** It places `/usr/lib/pse-riemann/pse-guard-helper`.
2. Check that root owns it and that it is only readable and executable:
   ```bash
   ls -l /usr/lib/pse-riemann/pse-guard-helper
   ```
   It must show `-rwxr-xr-x 1 root root`. If it does not, **stop**.
3. Find your user name:
   ```bash
   whoami
   ```
4. Open a new rule file **only through visudo**, because it checks the syntax and stops you from locking yourself out:
   ```bash
   sudo visudo -f /etc/sudoers.d/pse-riemann
   ```
5. Enter **exactly one line**, with your name in place of `YOUR_NAME`:
   ```
   YOUR_NAME ALL=(root) NOPASSWD: /usr/lib/pse-riemann/pse-guard-helper
   ```
   Save and exit.
6. Set the file's permissions:
   ```bash
   sudo chmod 0440 /etc/sudoers.d/pse-riemann
   ```
7. Check that it works without a password:
   ```bash
   sudo -n /usr/lib/pse-riemann/pse-guard-helper check
   ```
   It must print `ok ufw: ...`. If it shows `Status: inactive`, blocks have no effect: run `sudo ufw allow ssh` **first**, then `sudo ufw enable`. Otherwise you can lock yourself out from outside.
8. In the app: Guardian → "Provjeri prava čuvara". The red pill goes away.

## Removing the rule

```bash
sudo rm /etc/sudoers.d/pse-riemann
```

The guardian then goes back to alarms with commands and does nothing on its own.

## Lifting a block by hand

```bash
sudo ufw status numbered
sudo ufw delete deny from IP_ADDRESS to any
```
