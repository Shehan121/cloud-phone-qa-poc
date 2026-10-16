# Test results

Every task runs 3 times. `agent said ok` is what the agent claims , `checker read` is what the phone really shows. We only trust the second one.

## 1. The tour

```bash
python demo.py
```

![tour](screenshots/01_tour.png)

All four situations one after another :

- honest agent , working phone : PASS
- honest agent , Wi-Fi broken : Wi-Fi is a PRODUCT BUG , the rest still pass
- liar agent : AGENT MISTAKE
- flaky agent : AGENT MISTAKE

The WhatsApp task is always CAN'T TELL , the fake phone can't show it.

## 2. The liar agent

```bash
python demo.py --agent liar
```

![liar](screenshots/02_liar.png)

The agent says ok every time but the phone never changes. So it is an AGENT MISTAKE.

## 3. The flaky agent , time zone broken

```bash
python demo.py --agent flaky --broken timezone
```

![flaky](screenshots/03_flaky_timezone_broken.png)

Wi-Fi and dark theme only work on the 2nd try , so AGENT MISTAKE. The time zone never changes , even the direct path fails , so PRODUCT BUG.

## 4. The honest agent , Wi-Fi broken

```bash
python demo.py --agent honest --broken wifi
```

![wifi broken](screenshots/04_honest_wifi_broken.png)

The agent does the job but the phone stays off. So Wi-Fi is a PRODUCT BUG.

## Not tested

Claude as the agent ( `--agent claude` ) needs a real API key , so it is not here. The phone is fake too , so nothing talks to a real Mobilerun phone.
