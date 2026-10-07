import Foundation
import Darwin
let fm = FileManager.default
let args = CommandLine.arguments
if args.count != 4 { fatalError("expected path, device, inode") }
let path = args[1]
var before = stat()
if lstat(path, &before) != 0 { fatalError("source lstat failed") }
if String(before.st_dev) != args[2] || String(before.st_ino) != args[3] { fatalError("source identity changed") }
if (before.st_mode & S_IFMT) == S_IFLNK { fatalError("source is a symlink") }
var destination: NSURL?
do {
    try fm.trashItem(at: URL(fileURLWithPath: path), resultingItemURL: &destination)
    guard let target = destination?.path else { fatalError("native Trash returned no path") }
    var after = stat()
    if lstat(target, &after) != 0 { fatalError("destination lstat failed") }
    guard before.st_dev == after.st_dev && before.st_ino == after.st_ino else { fatalError("native move identity mismatch") }
    var old = stat()
    guard lstat(path, &old) != 0 && errno == ENOENT else { fatalError("source still exists") }
    let result: [String: Any] = ["operation": "FileManager.trashItem", "source": path, "destination": target, "device": String(after.st_dev), "inode": String(after.st_ino), "source_absent": true, "destination_identity_equal": true]
    let bytes = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
    print(String(data: bytes, encoding: .utf8)!)
} catch {
    fputs(String(describing: error) + "\n", stderr)
    exit(1)
}
