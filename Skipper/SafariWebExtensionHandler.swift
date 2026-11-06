import SafariServices

/// Native side of the YouTube skipper. The extension has no background page
/// and never sends native messages, so there is nothing to do here beyond
/// completing the request Safari hands us.
final class SafariWebExtensionHandler: NSObject, NSExtensionRequestHandling {
    func beginRequest(with context: NSExtensionContext) {
        context.completeRequest(returningItems: [], completionHandler: nil)
    }
}
