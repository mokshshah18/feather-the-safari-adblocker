import SwiftUI
import SafariServices
#if canImport(UIKit)
import UIKit
#endif

enum Feather {
    static let blockerID = "com.mokshshah.feather.blocker"
    static let skipperID = "com.mokshshah.feather.skipper"
}

@main
struct FeatherApp: App {
    var body: some Scene {
        #if os(macOS)
        WindowGroup { ContentView() }
            .windowResizability(.contentSize)
        #else
        WindowGroup { ContentView() }
        #endif
    }
}

struct ContentView: View {
    @State private var blockerOn: Bool?
    @State private var skipperOn: Bool?
    @State private var ruleCount: Int?
    @State private var message = ""

    var body: some View {
        #if os(macOS)
        panel
            .padding(24)
            .frame(width: 480)
            .onAppear(perform: refresh)
        #else
        ScrollView {
            panel.padding(20)
        }
        .onAppear(perform: refresh)
        #endif
    }

    private var panel: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Feather")
                .font(.system(size: 28, weight: .bold))
            Text("A content blocker for Safari. Safari compiles the rules once; no script from Feather runs on the pages you visit.")
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            Divider()

            StatusRow(title: "Feather Blocker", detail: blockerDetail, enabled: blockerOn)
            StatusRow(title: "Feather YouTube Skipper",
                      detail: "Skips in-video ads on youtube.com",
                      enabled: skipperOn)

            Divider()

            controls

            if !message.isEmpty {
                Text(message)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private var blockerDetail: String {
        ruleCount.map { "\($0) rules: ad and tracker hosts, ad slots on major sites" }
            ?? "Blocks ad and tracker requests, hides ad slots"
    }

    @ViewBuilder
    private var controls: some View {
        #if os(macOS)
        HStack {
            Button("Open Safari Extension Settings…", action: openSettings)
                .keyboardShortcut(.defaultAction)
            Button("Reload Rules", action: reload)
            Spacer()
            Button("Refresh", action: refresh)
        }
        #else
        VStack(alignment: .leading, spacing: 10) {
            Text("Turn both on in Settings › Apps › Safari › Extensions. On iOS 17 and earlier the path is Settings › Safari › Extensions.")
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Button("Open Settings", action: openSettings)
                Button("Reload Rules", action: reload)
                Spacer()
                Button("Refresh", action: refresh)
            }
            .buttonStyle(.bordered)
        }
        #endif
    }

    private func refresh() {
        SFContentBlockerManager.getStateOfContentBlocker(withIdentifier: Feather.blockerID) { state, error in
            DispatchQueue.main.async {
                blockerOn = state?.isEnabled
                if let error { message = error.localizedDescription }
            }
        }
        #if os(macOS)
        SFSafariExtensionManager.getStateOfSafariExtension(withIdentifier: Feather.skipperID) { state, _ in
            DispatchQueue.main.async { skipperOn = state?.isEnabled }
        }
        #endif
        ruleCount = countRules()
    }

    private func reload() {
        message = "Reloading…"
        SFContentBlockerManager.reloadContentBlocker(withIdentifier: Feather.blockerID) { error in
            DispatchQueue.main.async {
                message = error.map { "Reload failed: \($0.localizedDescription)" } ?? "Rules reloaded."
                refresh()
            }
        }
    }

    private func openSettings() {
        #if os(macOS)
        SFSafariApplication.showPreferencesForExtension(withIdentifier: Feather.blockerID) { error in
            if let error {
                DispatchQueue.main.async { message = error.localizedDescription }
            }
        }
        #else
        if let url = URL(string: UIApplication.openSettingsURLString) {
            UIApplication.shared.open(url)
        }
        #endif
    }

    /// Reads the rule list out of the embedded extension so the window can show its size.
    private func countRules() -> Int? {
        guard let plugins = Bundle.main.builtInPlugInsURL,
              let bundle = Bundle(url: plugins.appendingPathComponent("FeatherBlocker.appex")),
              let url = bundle.url(forResource: "blockerList", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let rules = try? JSONSerialization.jsonObject(with: data) as? [Any] else { return nil }
        return rules.count
    }
}

struct StatusRow: View {
    let title: String
    let detail: String
    let enabled: Bool?

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Circle()
                .fill(color)
                .frame(width: 10, height: 10)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.headline)
                Text(detail).font(.subheadline).foregroundStyle(.secondary)
            }
            Spacer()
            Text(label)
                .font(.subheadline.monospaced())
                .foregroundStyle(.secondary)
        }
    }

    private var color: Color {
        switch enabled {
        case .some(true): return .green
        case .some(false): return .orange
        case .none: return .gray
        }
    }

    private var label: String {
        switch enabled {
        case .some(true): return "ON"
        case .some(false): return "OFF"
        case .none: return ""
        }
    }
}
