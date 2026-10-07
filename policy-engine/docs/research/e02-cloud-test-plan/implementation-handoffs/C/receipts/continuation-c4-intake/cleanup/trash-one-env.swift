import Foundation
let path = CommandLine.arguments[1]
let source = URL(fileURLWithPath: path, isDirectory: true)
var resultingURL: NSURL?
try FileManager.default.trashItem(at: source, resultingItemURL: &resultingURL)
let result: [String: Any] = ["source": path, "trash_destination": resultingURL!.path!, "operation": "FileManager.default.trashItem", "trash_emptied": false]
let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
FileHandle.standardOutput.write(data)
FileHandle.standardOutput.write(Data("\n".utf8))
