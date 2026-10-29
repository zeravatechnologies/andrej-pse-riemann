# PSE Riemann — usko sudoers pravilo za SSH čuvara (korak po korak)

SSH čuvar sam radi samo **povratne** stvari: prekid jedne SSH sesije i **privremenu blokadu IP adrese na 24 h**, koja se sama skida. Za to mu treba root, ali samo za **jedan mali program** koji provjerava svaki argument:

```
/usr/lib/pse-riemann/pse-guard-helper   check | block-ip IP | unblock-ip IP | kill-session PID
```

Bez ovog pravila čuvar **ne radi ništa tiho**: diže veliki crveni alarm sa zvukom i tačnom komandom koju možeš sam pokrenuti.

Trajna blokada i gašenje SSH-a **nikad** nisu automatski. To su prijedlozi u „Čeka tvoju odluku“, sa tačnom komandom.

## Šta pravilo dozvoljava (i šta ne)

- Dozvoljava: da tvoj korisnik bez lozinke pokrene **samo** `pse-guard-helper`.
- Program odbija loopback (127.x, ::1), 0.0.0.0, broadcast, neispravne adrese i PID koji nije `sshd`.
- Aplikacija ga koristi samo ako pripada **root-u** i niko drugi ne može da ga mijenja. Ako bi bio u tvom home folderu, pravilo bi bilo rupa, pa ga aplikacija tada neće ni pokušati koristiti.
- Ne dozvoljava: ništa drugo. Nema `ufw` uopšte, nema `systemctl`, nema shell-a.

## Koraci

1. **Instaliraj .deb.** On postavlja `/usr/lib/pse-riemann/pse-guard-helper`.
2. Provjeri da pripada root-u i da je samo za čitanje i izvršavanje:
   ```bash
   ls -l /usr/lib/pse-riemann/pse-guard-helper
   ```
   Mora pisati `-rwxr-xr-x 1 root root`. Ako ne piše, **stani** i javi.
3. Saznaj svoje korisničko ime:
   ```bash
   whoami
   ```
4. Otvori novi fajl pravila **samo preko visudo**, jer on provjerava sintaksu i ne dozvoli da se zaključaš:
   ```bash
   sudo visudo -f /etc/sudoers.d/pse-riemann
   ```
5. Upiši **tačno jednu liniju**, sa svojim imenom umjesto `TVOJE_IME`:
   ```
   TVOJE_IME ALL=(root) NOPASSWD: /usr/lib/pse-riemann/pse-guard-helper
   ```
   Snimi i izađi.
6. Postavi prava fajla:
   ```bash
   sudo chmod 0440 /etc/sudoers.d/pse-riemann
   ```
7. Provjera bez lozinke:
   ```bash
   sudo -n /usr/lib/pse-riemann/pse-guard-helper check
   ```
   Mora ispisati `ok ufw: ...`. Ako piše `Status: inactive`, ufw je ugašen i blokade nemaju efekta. Upali ga sa `sudo ufw enable`, ali **prvo** dozvoli SSH sa `sudo ufw allow ssh`, inače se možeš zaključati izvana.
8. U aplikaciji: Guardian → „Provjeri prava čuvara“. Crvena pilula nestaje.

## Kako se pravilo uklanja

```bash
sudo rm /etc/sudoers.d/pse-riemann
```

Čuvar se tada vraća na alarme sa komandama i ništa ne radi sam.

## Ručno skidanje blokade (ako zatreba)

```bash
sudo ufw status numbered
sudo ufw delete deny from IP_ADRESA to any
```
