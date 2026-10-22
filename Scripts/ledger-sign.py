"""Sign index.json on the Ledger (SSH/PGP Agent app, Ed25519; sandbox plan §7, M0 0.12).

Usage: ledger-sign.py pubkey          -> prints the store key (OpenSSH form, as in key.pub)
       ledger-sign.py sign index.json -> index.json.sig = base64 Ed25519 signature over SHA-256(index.json)
The app's generic-hash command (INS 06, P2 0x02) hashes the data on the device and signs the hash after
you approve it there. Needs `pip install ledgerblue`, the Ledger unlocked and the app open.
APDUs from trezor-agent's last Ledger driver (romanz/trezor-agent@b782b610a9, libagent/device/ledger.py).
"""
import base64, os, struct, sys
from ledgerblue import comm

# SLIP-13-style hardened path for the store key (fixed, so the key is reproducible from the seed).
PATH = [13 | 0x80000000, 0x76326d61 | 0x80000000, 1 | 0x80000000, 0x80000000, 0x80000000]
KEY_PUB = os.path.join(os.path.dirname(__file__), "..", "key.pub")

def path_bytes():
    return bytes([len(PATH)]) + b"".join(struct.pack(">I", e) for e in PATH)

def ssh_string(b):
    return struct.pack(">I", len(b)) + b

def pubkey(dongle):
    p = path_bytes()
    r = bytearray(dongle.exchange(bytes([0x80, 0x02, 0x00, 0x02, len(p)]) + p))[1:]
    # reply: 0x04 || X (32, big endian) || Y (32, big endian) -> Ed25519 = Y little endian with X's sign bit
    x, y = r[1:33], bytearray(r[33:65][::-1])
    if x[31] & 1:
        y[31] |= 0x80
    return bytes(y)

def sign(dongle, blob):
    p = path_bytes()
    off, res = 0, None
    while True:
        data = p if off == 0 else b""
        n = min(len(blob) - off, 255 - len(data))
        data += blob[off:off + n]
        last = off + n == len(blob)
        p1 = (0x80 if last else 0x00) | (0x00 if off == 0 else 0x01)
        res = dongle.exchange(bytes([0x80, 0x06, p1, 0x02, len(data)]) + data)
        off += n
        if last:
            return bytes(res[:64])

def openssh(pk):
    return "ssh-ed25519 " + base64.b64encode(ssh_string(b"ssh-ed25519") + ssh_string(pk)).decode() + " v2mac-store"

def main():
    dongle = comm.getDongle()
    pk = pubkey(dongle)
    if sys.argv[1:2] == ["pubkey"]:
        return print(openssh(pk))
    if sys.argv[1:2] != ["sign"] or len(sys.argv) != 3:
        sys.exit(__doc__)
    # The helper pins this key: signing with another Ledger or seed would make an index nobody accepts.
    if open(KEY_PUB).read().split()[1] != openssh(pk).split()[1]:
        sys.exit("This Ledger's store key is not the one in key.pub.")
    path = sys.argv[2]
    sig = sign(dongle, open(path, "rb").read())
    with open(path + ".sig", "w") as f:
        f.write(base64.b64encode(sig).decode() + "\n")
    print("wrote", path + ".sig")

main()
