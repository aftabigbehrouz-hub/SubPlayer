#!/usr/bin/env python3
"""
SubPlayer - create an activation code for a buyer's phone (owner only).

    pip install cryptography
    python make_activation_code.py SUBPLAYER_LICENCE_PRIVATE_KEY.txt ABCDE-FGHIJ "Buyer Name"

The buyer finds the DEVICE CODE on SubPlayer's activation screen. The printed code
works only on that phone. Keep the private key file secret: whoever has it can
create codes. (You can also create codes inside the app: Settings > Owner tools.)
"""
import base64, sys
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b32(data: bytes) -> str:
    return base64.b32encode(data).decode().rstrip("=")


def make(private_key_b64: str, device: str, name: str) -> str:
    key = serialization.load_der_private_key(base64.b64decode("".join(private_key_b64.split())), password=None)
    payload = f"SP1|{device.strip().upper()}|{name.strip()}".encode("utf-8")
    sig = key.sign(payload, ec.ECDSA(hashes.SHA256()))
    return b32(payload) + "." + b32(sig)


def check(public_key_b64: str, code: str, device: str):
    pub = serialization.load_der_public_key(base64.b64decode(public_key_b64))
    p, s = code.split(".")
    pad = lambda x: x + "=" * (-len(x) % 8)
    payload, sig = base64.b32decode(pad(p)), base64.b32decode(pad(s))
    pub.verify(sig, payload, ec.ECDSA(hashes.SHA256()))
    f = payload.decode("utf-8").split("|", 2)
    assert f[0] == "SP1" and f[1] == device.strip().upper()
    return f[2]


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    key_file, device, name = sys.argv[1:]
    code = make(open(key_file, encoding="utf-8").read(), device, name)
    print("\nActivation code for", name, "(device", device.upper() + "):\n")
    print(code)
    print("\nSend this whole line to the buyer; they paste it on the activation screen.\n")
