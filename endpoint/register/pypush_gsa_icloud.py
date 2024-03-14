import urllib3
from getpass import getpass
import plistlib as plist
import json
import uuid
import pbkdf2
import requests
import hashlib
import hmac
import base64
import locale
import logging
from datetime import datetime
import srp._pysrp as srp
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from Crypto.Hash import SHA256
import config
# macless-haystack-flipper - Imports
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
from urllib.parse import parse_qs
import threading

#
# macless-haystack-flipper - Create HTTP server to handle credentials
#

form_html = """
    <html><body>
    <form method="post">
    {inputs}
    <input type="submit" value="Submit">
    </form></body></html>
"""

class ServerHandler(BaseHTTPRequestHandler):
    form_fields = ""

    def _send_form(self, inputs):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(bytes(form_html.format(inputs=inputs), "utf-8"))

    def do_GET(self):
        if self.path == '/':
            self._send_form(self.form_fields)
        elif self.path == '/redirect':
            self._send_redirect()
        elif self.path == '/finish':
            self._send_finish()

    def _send_redirect(self):
        host = self.headers['Host'] if 'Host' in self.headers else "localhost:6176"
        message = f"""Please wait, preparing the next prompt.
If the page does not reload, wait 10 seconds. Then browse to <a href="http://{host}">http://{host}</a> in a new tab."""
        refresh_header = '<meta http-equiv="refresh" content="5;url=/" />'
        self._send_response(f'<html><head>{refresh_header}</head><body>{message}</body></html>')

    def _send_response(self, content):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(bytes(content, "utf-8"))

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        user_input = parse_qs(post_data.decode())
        self.server.user_input = user_input  # Save the data in the server instance
        self.send_response(302)
        self.send_header('Location', '/redirect')
        self.end_headers()

    def log_message(self, format, *args):
        return  # Suppress logging of GET and POST requests

def start_server(form_fields):
    handler = type('CustomHandler', (ServerHandler,), {"form_fields": form_fields})
    server_address = ('', 6176)
    httpd = HTTPServer(server_address, handler)

    def server_thread():
        httpd.serve_forever()

    t = threading.Thread(target=server_thread)
    t.daemon = True
    t.start()
    return httpd

def shutdown_server(server):
    server.shutdown()

#
# macless-haystack-flipper - Functions to get user input
#

def get_username():
    form_fields = 'Apple ID: <input name="username" type="text"><br>'
    server = start_server(form_fields)
    while not hasattr(server, 'user_input'):
        pass  # Wait until input is received
    shutdown_server(server)
    return server.user_input['username'][0]

def get_password():
    form_fields = 'Password: <input name="password" type="password"><br>'
    server = start_server(form_fields)
    while not hasattr(server, 'user_input'):
        pass
    shutdown_server(server)
    return server.user_input['password'][0]

def get_2fa_code():
    form_fields = '2FA Code: <input name="code" type="text"><br>'
    server = start_server(form_fields)
    while not hasattr(server, 'user_input'):
        pass
    shutdown_server(server)
    return server.user_input['code'][0]

def get_2fa_method():
    form_fields = '''
        Choose 2FA Method:<br>
        <input type="radio" name="method" value="sms"> SMS<br>
        <input type="radio" name="method" value="trusted_device"> Trusted Device<br>
    '''
    server = start_server(form_fields)
    while not hasattr(server, 'user_input'):
        pass
    shutdown_server(server)
    return server.user_input['method'][0]

#
#
#

# Created here so that it is consistent
USER_ID = uuid.uuid4()
DEVICE_ID = uuid.uuid4()

# Configure SRP library for compatibility with Apple's implementation
srp.rfc5054_enable()
srp.no_username_in_x()

# Disable SSL Warning
urllib3.disable_warnings()


logger = logging.getLogger()


def icloud_login_mobileme(username='', password='', second_factor='sms'):
    if not username:
        # username = input('Apple ID: ')
        username = get_username() # macless-haystack-flipper - Replace with web prompt
    if not password:
        # password = getpass('Password: ')
        password = get_password() # macless-haystack-flipper - Replace with web prompt
    second_factor = get_2fa_method() # macless-haystack-flipper - Prompt the user to choose between 2FA methods
    g = gsa_authenticate(username, password, second_factor)
    pet = g["t"]["com.apple.gs.idms.pet"]["token"]
    adsid = g["adsid"]

    data = {
        "apple-id": username,
        "delegates": {"com.apple.mobileme": {}},
        "password": pet,
        "client-id": str(USER_ID),
    }
    data = plist.dumps(data)
    headers = {
        "X-Apple-ADSID": adsid,
        "User-Agent": "com.apple.iCloudHelper/282 CFNetwork/1408.0.4 Darwin/22.5.0",
        "X-Mme-Client-Info": '<MacBookPro18,3> <Mac OS X;13.4.1;22F8> <com.apple.AOSKit/282 (com.apple.accountsd/113)>'
    }
    headers.update(generate_anisette_headers())

    r = requests.post(
        "https://setup.icloud.com/setup/iosbuddy/loginDelegates",
        auth=(username, pet),
        data=data,
        headers=headers,
        verify=False,
    )
    return plist.loads(r.content)


def gsa_authenticate(username, password, second_factor='sms'):
    # Password is None as we'll provide it later
    usr = srp.User(username, bytes(), hash_alg=srp.SHA256, ng_type=srp.NG_2048)
    _, A = usr.start_authentication()

    r = gsa_authenticated_request(
        {"A2k": A, "ps": ["s2k", "s2k_fo"], "u": username, "o": "init"})

    if r["sp"] != "s2k":
        logger.warn(
            f"This implementation only supports s2k. Server returned {r['sp']}")
        return

    # Change the password out from under the SRP library, as we couldn't calculate it without the salt.
    usr.p = encrypt_password(password, r["s"], r["i"])

    M = usr.process_challenge(r["s"], r["B"])

    # Make sure we processed the challenge correctly
    if M is None:
        logger.error("Failed to process challenge")
        return

    r = gsa_authenticated_request(
        {"c": r["c"], "M1": M, "u": username, "o": "complete"})

    # Make sure that the server's session key matches our session key (and thus that they are not an imposter)
    usr.verify_session(r["M2"])
    if not usr.authenticated():
        logger.error("Failed to verify session")
        return

    spd = decrypt_cbc(usr, r["spd"])
    # For some reason plistlib doesn't accept it without the header...
    PLISTHEADER = b"""\
<?xml version='1.0' encoding='UTF-8'?>
<!DOCTYPE plist PUBLIC '-//Apple//DTD PLIST 1.0//EN' 'http://www.apple.com/DTDs/PropertyList-1.0.dtd'>
"""
    spd = plist.loads(PLISTHEADER + spd)

    if "au" in r["Status"] and r["Status"]["au"] in ["trustedDeviceSecondaryAuth", "secondaryAuth"]:
        logger.info("2FA required, requesting code")
        # Replace bytes with strings
        for k, v in spd.items():
            if isinstance(v, bytes):
                spd[k] = base64.b64encode(v).decode()
        if second_factor == 'sms':
            sms_second_factor(spd["adsid"], spd["GsIdmsToken"])
        elif second_factor == 'trusted_device':
            trusted_second_factor(spd["adsid"], spd["GsIdmsToken"])
            return
        return gsa_authenticate(username, password, second_factor)
    elif "au" in r["Status"]:
        logger.error(f"Unknown auth value {r['Status']['au']}")
        return
    else:
        return spd


def gsa_authenticated_request(parameters):
    body = {
        "Header": {"Version": "1.0.1"},
        "Request": {"cpd": generate_cpd()},
    }
    body["Request"].update(parameters)

    headers = {
        "Content-Type": "text/x-xml-plist",
        "Accept": "*/*",
        "User-Agent": "akd/1.0 CFNetwork/978.0.7 Darwin/18.7.0",
        "X-MMe-Client-Info": '<MacBookPro18,3> <Mac OS X;13.4.1;22F8> <com.apple.AOSKit/282 (com.apple.dt.Xcode/3594.4.19)>'
    }

    resp = requests.post(
        "https://gsa.apple.com/grandslam/GsService2",
        headers=headers,
        data=plist.dumps(body),
        verify=False,
        timeout=5,
    )

    return plist.loads(resp.content)["Response"]


def generate_cpd():
    cpd = {
        # Many of these values are not strictly necessary, but may be tracked by Apple
        "bootstrap": True,  # All implementations set this to true
        "icscrec": True,  # Only AltServer sets this to true
        "pbe": False,  # All implementations explicitly set this to false
        "prkgen": True,  # I've also seen ckgen
        "svct": "iCloud",  # In certian circumstances, this can be 'iTunes' or 'iCloud'
    }

    cpd.update(generate_anisette_headers())
    return cpd


def generate_anisette_headers():
    

    logger.debug(
        f'Querying {config.getAnisetteServer()} for an anisette server')
    h = json.loads(requests.get(config.getAnisetteServer(), timeout=5).text)
    a = {"X-Apple-I-MD": h["X-Apple-I-MD"],
         "X-Apple-I-MD-M": h["X-Apple-I-MD-M"]}
    a.update(generate_meta_headers(user_id=USER_ID, device_id=DEVICE_ID))
    return a


def generate_meta_headers(serial="0", user_id=uuid.uuid4(), device_id=uuid.uuid4()):
    return {
        "X-Apple-I-Client-Time": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "X-Apple-I-TimeZone": str(datetime.utcnow().astimezone().tzinfo),
        "loc": locale.getdefaultlocale()[0] or "en_US",
        "X-Apple-Locale": locale.getdefaultlocale()[0] or "en_US",
        "X-Apple-I-MD-RINFO": "17106176",  # either 17106176 or 50660608
        "X-Apple-I-MD-LU": base64.b64encode(str(user_id).upper().encode()).decode(),
        "X-Mme-Device-Id": str(device_id).upper(),
        "X-Apple-I-SRL-NO": serial,  # Serial number
    }


def encrypt_password(password, salt, iterations):
    p = hashlib.sha256(password.encode("utf-8")).digest()
    return pbkdf2.PBKDF2(p, salt, iterations, SHA256).read(32)


def create_session_key(usr, name):
    k = usr.get_session_key()
    if k is None:
        raise Exception("No session key")
    return hmac.new(k, name.encode(), hashlib.sha256).digest()


def decrypt_cbc(usr, data):
    extra_data_key = create_session_key(usr, "extra data key:")
    extra_data_iv = create_session_key(usr, "extra data iv:")
    # Get only the first 16 bytes of the iv
    extra_data_iv = extra_data_iv[:16]

    # Decrypt with AES CBC
    cipher = Cipher(algorithms.AES(extra_data_key), modes.CBC(extra_data_iv))
    decryptor = cipher.decryptor()
    data = decryptor.update(data) + decryptor.finalize()
    # Remove PKCS#7 padding
    padder = padding.PKCS7(128).unpadder()
    return padder.update(data) + padder.finalize()


def trusted_second_factor(dsid, idms_token):
    identity_token = base64.b64encode(
        (dsid + ":" + idms_token).encode()).decode()

    headers = {
        "Content-Type": "text/x-xml-plist",
        "User-Agent": "Xcode",
        "Accept": "text/x-xml-plist",
        "Accept-Language": "en-us",
        "X-Apple-Identity-Token": identity_token,
        "X-Apple-App-Info": "com.apple.gs.xcode.auth",
        "X-Xcode-Version": "11.2 (11B41)",
        "X-Mme-Client-Info": '<MacBookPro18,3> <Mac OS X;13.4.1;22F8> <com.apple.AOSKit/282 (com.apple.dt.Xcode/3594.4.19)>'
    }

    headers.update(generate_anisette_headers())

    # This will trigger the 2FA prompt on trusted devices
    # We don't care about the response, it's just some HTML with a form for entering the code
    # Easier to just use a text prompt
    requests.get(
        "https://gsa.apple.com/auth/verify/trusteddevice",
        headers=headers,
        verify=False,
        timeout=10,
    )

    # Prompt for the 2FA code. It's just a string like '123456', no dashes or spaces
    #code = getpass("Enter 2FA code: ")
    logger.info("prompting for 2FA from user via trusted device")
    code = get_2fa_code() # macless-haystack-flipper - Replace with web prompt
    headers["security-code"] = code

    # Send the 2FA code to Apple
    resp = requests.get(
        "https://gsa.apple.com/grandslam/GsService2/validate",
        headers=headers,
        verify=False,
        timeout=10,
    )
    if resp.ok:
        logger.info("2FA code from trusted device sent successfully")


def sms_second_factor(dsid, idms_token):
    identity_token = base64.b64encode(
        (dsid + ":" + idms_token).encode()).decode()

    # TODO: Actually do this request to get user prompt data
    # a = requests.get("https://gsa.apple.com/auth", verify=False)
    # This request isn't strictly necessary though,
    # and most accounts should have their id 1 SMS, if not contribute ;)

    headers = {
        "User-Agent": "Xcode",
        "Accept-Language": "en-us",
        "X-Apple-Identity-Token": identity_token,
        "X-Apple-App-Info": "com.apple.gs.xcode.auth",
        "X-Xcode-Version": "11.2 (11B41)",
        "X-Mme-Client-Info": '<MacBookPro18,3> <Mac OS X;13.4.1;22F8> <com.apple.AOSKit/282 (com.apple.dt.Xcode/3594.4.19)>'
    }

    headers.update(generate_anisette_headers())

    # TODO: Actually get the correct id, probably in the above GET
    body = {"phoneNumber": {"id": 1}, "mode": "sms"}

    # This will send the 2FA code to the user's phone over SMS
    # We don't care about the response, it's just some HTML with a form for entering the code
    # Easier to just use a text prompt
    t = requests.put(
        "https://gsa.apple.com/auth/verify/phone/",
        json=body,
        headers=headers,
        verify=False,
        timeout=5
    )
    # Prompt for the 2FA code. It's just a string like '123456', no dashes or spaces
    # code = input("Enter 2FA code: ")
    logger.info("prompting for 2FA from user via SMS")
    code = get_2fa_code() # macless-haystack-flipper - Replace with web prompt

    body['securityCode'] = {'code': code}

    # Send the 2FA code to Apple
    resp = requests.post(
        "https://gsa.apple.com/auth/verify/phone/securitycode",
        json=body,
        headers=headers,
        verify=False,
        timeout=5,
    )
    if resp.ok:
        logger.info("2FA code from SMS sent successfully")
