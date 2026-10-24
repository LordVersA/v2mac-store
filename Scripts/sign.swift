// Sign index.json with the store key in this Mac's login Keychain (sandbox plan §7).
//
// Usage: swift Scripts/sign.swift keygen          -> makes the key once, writes key.pub
//        swift Scripts/sign.swift pubkey          -> prints the store key (OpenSSH form, as in key.pub)
//        swift Scripts/sign.swift sign index.json -> index.json.sig = base64 Ed25519 signature over SHA-256(index.json)
//        swift Scripts/sign.swift selftest
// The private key is the Keychain item "v2mac-store" with no trusted apps, so every use asks for your
// login password. Back it up on paper: `security find-generic-password -s v2mac-store -w` prints it.
import CryptoKit
import Foundation

let service = "v2mac-store"
let keyPub = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("../key.pub").standardized

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

func security(_ args: [String]) -> (status: Int32, out: String) {
    let p = Process(), pipe = Pipe()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/security")
    p.arguments = args
    p.standardOutput = pipe
    try! p.run()
    let out = String(decoding: pipe.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
    p.waitUntilExit()
    return (p.terminationStatus, out.trimmingCharacters(in: .whitespacesAndNewlines))
}

func storedKey() -> Curve25519.Signing.PrivateKey {
    let r = security(["find-generic-password", "-s", service, "-w"])
    guard r.status == 0 else { fail("No store key in the Keychain (or access denied). Make one with keygen.") }
    guard let raw = Data(base64Encoded: r.out), let key = try? Curve25519.Signing.PrivateKey(rawRepresentation: raw) else {
        fail("The Keychain item \(service) is not an Ed25519 key.")
    }
    return key
}

func openssh(_ key: Curve25519.Signing.PublicKey) -> String {
    func string(_ b: Data) -> Data { withUnsafeBytes(of: UInt32(b.count).bigEndian) { Data($0) } + b }
    return "ssh-ed25519 " + (string(Data("ssh-ed25519".utf8)) + string(key.rawRepresentation)).base64EncodedString() + " v2mac-store"
}

func signature(_ key: Curve25519.Signing.PrivateKey, _ data: Data) -> String {
    try! key.signature(for: Data(SHA256.hash(data: data))).base64EncodedString()
}

let args = Array(CommandLine.arguments.dropFirst())
switch args.first {
case "keygen":
    if security(["find-generic-password", "-s", service, "-a", "index"]).status == 0 { fail("A store key already exists; refusing to replace it.") }
    let key = Curve25519.Signing.PrivateKey()
    // -T "" trusts no app: reading it always asks for the login password.
    guard security(["add-generic-password", "-s", service, "-a", "index", "-T", "", "-w", key.rawRepresentation.base64EncodedString()]).status == 0
    else { fail("Couldn't add the key to the Keychain.") }
    try! (openssh(key.publicKey) + "\n").write(to: keyPub, atomically: true, encoding: .utf8)
    print("wrote key.pub; helper key:", key.publicKey.rawRepresentation.base64EncodedString())
case "pubkey":
    print(openssh(storedKey().publicKey))
case "sign" where args.count == 2:
    let key = storedKey()
    // The helper pins key.pub: a signature from another key makes an index nobody accepts.
    guard let pinned = try? String(contentsOf: keyPub, encoding: .utf8), pinned.split(separator: " ")[1] == openssh(key.publicKey).split(separator: " ")[1]
    else { fail("The Keychain's store key is not the one in key.pub.") }
    guard let data = FileManager.default.contents(atPath: args[1]) else { fail("Can't read \(args[1]).") }
    try! (signature(key, data) + "\n").write(toFile: args[1] + ".sig", atomically: true, encoding: .utf8)
    print("wrote", args[1] + ".sig")
case "selftest":
    let key = Curve25519.Signing.PrivateKey(), data = Data("{\"version\":1}".utf8)
    let sig = Data(base64Encoded: signature(key, data))!
    // Same check as the helper's Store.verify.
    assert(key.publicKey.isValidSignature(sig, for: Data(SHA256.hash(data: data))))
    assert(!key.publicKey.isValidSignature(sig, for: Data(SHA256.hash(data: data + Data([0])))))
    assert(openssh(key.publicKey).hasPrefix("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI"))
    print("selftest ok")
default:
    fail("usage: swift Scripts/sign.swift keygen | pubkey | sign index.json | selftest")
}
