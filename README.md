# Macless-Haystack-Flipper

The goal of this project is to create a method that allows users of the Flipper Zero to easily set up macless-haystack locally, for use with the FindMyFlipper app.

Functionally, this is primarily a fork of the endpoint container provided by macless-hackstack.

The major change is that container is that the Username, Password, and MFA code requested for the Apple account are no longer input from the terminal in interactive mode. Instead, this is done through the web.

I made this change, because users of the Flipper Zero have reported that the server doesn't work to query the device properly after the container is restarted. Instead, the container provided from this project will prompt for authentication each time it starts.

Keep in mind, the credentials are sent to your local server in plain text from your browser. As such, you should only authenticate within your local machine, or inside of a network that you trust.

I also created a Dockerfile to run the web application from macless-haystack locally, as some Flipper Zero users have had trouble with the app publically hosted on the web.

## Table of Contents

- [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Flipper setup](#flipper-setup)
  - [Server setup](#server-setup)
  - [Frontend setup](#frontend-setup)
- [Included projects and changes](#included-projects-and-changes)

## Setup

These instructions have been customized for use with the Flipper Zero.

<details><summary>1. Prerequisites</summary>

## Prerequisites

- [Docker](https://www.docker.com/) installed
- [Python3](https://www.python.org/) and [pip3](https://pypi.org/project/pip/) installed
- Apple-ID with F2A (mobile or sms) enabled
- Flipper Zero with [MFW](https://github.com/Next-Flip/Momentum-Firmware) installed

---

</details>

<details><summary>2. Flipper setup</summary>

## Flipper setup

1. Head over to the [FindMyFlipper](https://github.com/dchristl/macless-haystack/releases/latest) repo and download `generate_keys.py` from the KeyGeneration folder.

2. Execute the `generate_keys.py` script to generate your keypair. (Note: dependency `cryptography` is needed. Install it with `pip install cryptography`)

3. Follow the prompts and afterward you should have a .keys file generated in a keys subfolder.

4. Put the .keys file onto the Flipper, inside the AppsData/FindMyFlipper folder. Alternatively, you can manually enter this information into the FindMyFlipper app.

5. Open the FindMyFlipper app after starting the Flipper with the SD Card re-inserted.

6. Press the right button to open the config menu, and then select "Import Tag From File".

7. Select "OpenHaystack.keys" and then select the keys file.

8. Start broadcasting using the FindMyFlipper app.

---

</details>

<details><summary>3. Server setup (Docker Hub)</summary>

## Server setup

0. Alternatively: You can build the containers yourself using the Dockerfile in "endpoint" to build "macless-haystack-flipper", and "web" to build "macless-flipper-web". To make set up easier, I have pre-built them and created a compose file to simplify this.

1. Create a new Docker network

```bash
docker network create mh-network
```

2. Create a working directory and make a file called "docker-compose.yml" with these contents:

```docker-compose.yml
version: '3'
services:
  anisette:
    image: dadoum/anisette-v3-server:latest
    container_name: anisette
    restart: unless-stopped
    ports:
      - "6969:6969"
    networks:
      - mh-network

  macless-haystack:
    image: sourcebunny/macless-haystack-flipper:latest
    container_name: macless-haystack-flipper
    restart: unless-stopped
    ports:
      - "6176:6176"
    networks:
      - mh-network

  macless-haystack-web:
    image: sourcebunny/macless-haystack-web:latest
    container_name: macless-haystack-web
    restart: unless-stopped
    ports:
      - "9443:443"
    networks:
      - mh-network

networks:
  mh-network:
    external: true
```

3. Start the Docker containers

```bash
docker-compose up -d
```

4. Browse to your server on port 6176. For example, http://localhost:6176

5. You will be asked for your Apple-ID, password and your 2FA.

6. Test the server by browsing to https://localhost:6176, you should see "Nothing to see here"

###### If the containers are restarted, you will need to re-authenticate using steps 4 - 6.

---

</details>

<details><summary>4. Frontend setup</summary>

## Frontend setup

This repository includes a Dockerfile that hosts the web application locally.

This should already be running if you started the included docker-compose.yml file, and you can follow the steps to get it working.

1. Browse to your server with HTTPS on port 9443. For example, https://localhost:9443

2. Go to the settings, and correct the URL to match your server, on port 6176. For example, https://localhost:6176

3. Press "OK", and return to the main page.

4. Press the "+" button to add a new device.

5. Select "Import Accessory".

6. Pick any 7 digit ID number, and use it for the ID field. Other numbers and lengths may also work.

7. Name the device based on your preference. This will be displayed within the page.

8. Copy the Private Key from the ".keys" file you generated into the "Private Key (Base64)" field.

9. Enable both the "Is Active" and "Is Deployed" checkboxes.

10. Press the "Import" button.

11. Press the "Refresh" button. If you don't see your device's location, try again after some time. You can also try moving closer to a device such as an Apple iPhone.

---

</details>

## Included projects and changes

Included projects are (Credits goes to them for the hard work):

- The original [Openhaystack](https://github.com/seemoo-lab/openhaystack)
  - Stripped down to the mobile application (Android) and ESP32 firmware. ESP32 firmware combined with FindYou project and optimizations in power usage.
  - Android application
  - ESP32 firmware
- [Biemster's FindMy](https://github.com/biemster/FindMy)
  - Customization in keypair generator to output an array for the ESP32 firmware and a json for import in the Android application.
  - The standalone python webserver for fetching the FindMy reports
- [Positive security's Find you](https://github.com/positive-security/find-you)
  - ESP32 firmware customization for battery optimization
- [acalatrava's OpenHaystack-Fimware alternative](https://github.com/acalatrava/openhaystack-firmware)
  - NRF5x firmware customization for battery optimization
- [dchrist's macless-haystack](https://github.com/dchristl/macless-haystack)


[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)


## Disclaimer

This repository is for research purposes only, the use of this code is your responsibility.

I take NO responsibility and/or liability for how you choose to use any of the source code available here. By using any of the files available in this repository, you understand that you are AGREEING TO USE AT YOUR OWN RISK. Once again, ALL files available here are for EDUCATION and/or RESEARCH purposes ONLY.
