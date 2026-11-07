import Foundation

/// Hands Safari the compiled rule list. Safari calls this once when the
/// blocker is enabled or reloaded, compiles the JSON to bytecode, and then
/// evaluates requests itself. No code from this extension runs per page.
final class ContentBlockerRequestHandler: NSObject, NSExtensionRequestHandling {
    func beginRequest(with context: NSExtensionContext) {
        guard let url = Bundle.main.url(forResource: "blockerList", withExtension: "json"),
              let attachment = NSItemProvider(contentsOf: url) else {
            context.cancelRequest(withError: CocoaError(.fileNoSuchFile))
            return
        }
        let item = NSExtensionItem()
        item.attachments = [attachment]
        context.completeRequest(returningItems: [item], completionHandler: nil)
    }
}
