#!/usr/bin/env ruby
# Regenerates Feather.xcodeproj from the files on disk.
#
#   gem install xcodeproj
#   ruby tools/gen_project.rb
#
# The checked-in project is the output of this script. Edit the script, not
# the pbxproj, when adding files or changing build settings.
#
# Six targets, three per platform: the container app, the content blocker
# extension, and the YouTube skipper web extension. Source files, the rule
# list, the web-extension resources and the asset catalog are shared.
require 'xcodeproj'
require 'fileutils'

ROOT = File.expand_path('..', __dir__)
PROJECT_PATH = File.join(ROOT, 'Feather.xcodeproj')
BUNDLE_PREFIX = 'com.mokshshah.feather'
MACOS_DEPLOYMENT_TARGET = '13.0'
IOS_DEPLOYMENT_TARGET = '16.4' # first iOS Safari with Manifest V3 web extensions

PLATFORMS = {
  macos: {
    sym: :osx, label: 'macOS', deploy: MACOS_DEPLOYMENT_TARGET,
    settings: {
      'SDKROOT' => 'macosx',
      'MACOSX_DEPLOYMENT_TARGET' => MACOS_DEPLOYMENT_TARGET,
      'CODE_SIGN_IDENTITY' => '-', # "Sign to Run Locally"; pick a team in Xcode for a real certificate
      'ENABLE_HARDENED_RUNTIME' => 'YES',
      'COMBINE_HIDPI_IMAGES' => 'YES',
    },
    app_rpath: ['$(inherited)', '@executable_path/../Frameworks'],
    ext_rpath: ['$(inherited)', '@executable_path/../Frameworks', '@executable_path/../../../../Frameworks'],
  },
  ios: {
    sym: :ios, label: 'iOS', deploy: IOS_DEPLOYMENT_TARGET,
    settings: {
      'SDKROOT' => 'iphoneos',
      'IPHONEOS_DEPLOYMENT_TARGET' => IOS_DEPLOYMENT_TARGET,
      'TARGETED_DEVICE_FAMILY' => '1,2',
      'SUPPORTS_MACCATALYST' => 'NO',
    },
    app_rpath: ['$(inherited)', '@executable_path/Frameworks'],
    ext_rpath: ['$(inherited)', '@executable_path/Frameworks', '@executable_path/../../Frameworks'],
  },
}.freeze

def configure(target, settings)
  target.build_configurations.each { |c| c.build_settings.merge!(settings) }
end

FileUtils.rm_rf(PROJECT_PATH)
project = Xcodeproj::Project.new(PROJECT_PATH)
project.root_object.attributes['LastUpgradeCheck'] = '1500'
project.root_object.known_regions = %w[en Base]

project.build_configurations.each do |config|
  config.build_settings.merge!(
    'SWIFT_VERSION' => '5.0',
    'CODE_SIGN_STYLE' => 'Automatic',
    'CURRENT_PROJECT_VERSION' => '1',
    'MARKETING_VERSION' => '1.0.0',
    'ENABLE_USER_SCRIPT_SANDBOXING' => 'YES',
    'DEAD_CODE_STRIPPING' => 'YES',
    'GENERATE_INFOPLIST_FILE' => 'NO',
    'LOCALIZATION_PREFERS_STRING_CATALOGS' => 'YES',
  )
end

# ---- File references, shared across platforms ---------------------------------

app_group = project.main_group.new_group('App', 'App')
app_swift = app_group.new_file('FeatherApp.swift')
assets = app_group.new_file('Assets.xcassets')
%w[Info-macOS.plist Info-iOS.plist Feather.entitlements].each { |f| app_group.new_file(f) }

blocker_group = project.main_group.new_group('ContentBlocker', 'ContentBlocker')
blocker_swift = blocker_group.new_file('ContentBlockerRequestHandler.swift')
blocker_json = blocker_group.new_file('blockerList.json')
%w[Info.plist FeatherBlocker.entitlements].each { |f| blocker_group.new_file(f) }

skipper_group = project.main_group.new_group('Skipper', 'Skipper')
skipper_swift = skipper_group.new_file('SafariWebExtensionHandler.swift')
%w[Info.plist FeatherSkipper.entitlements].each { |f| skipper_group.new_file(f) }
resources_group = skipper_group.new_group('Resources', 'Resources')
skipper_resources = %w[manifest.json youtube.js].map { |f| resources_group.new_file(f) }

rules_group = project.main_group.new_group('Rules', 'rules')
%w[domains.txt urls.txt cosmetic.txt].each { |f| rules_group.new_file(f) }

tools_group = project.main_group.new_group('Tools', 'tools')
%w[build_rules.py test_rules.py test_skipper.mjs gen_icons.py gen_project.rb].each { |f| tools_group.new_file(f) }

# ---- Targets -------------------------------------------------------------------

project.save # the scheme writer needs the project directory to exist

PLATFORMS.each do |key, p|
  app = project.new_target(:application, "Feather (#{p[:label]})", p[:sym], p[:deploy], nil, :swift, 'Feather')
  configure(app, p[:settings].merge(
    'PRODUCT_NAME' => 'Feather',
    'PRODUCT_BUNDLE_IDENTIFIER' => BUNDLE_PREFIX,
    'INFOPLIST_FILE' => "App/Info-#{p[:label]}.plist",
    'ASSETCATALOG_COMPILER_APPICON_NAME' => 'AppIcon',
    'LD_RUNPATH_SEARCH_PATHS' => p[:app_rpath],
    'ENABLE_PREVIEWS' => 'YES',
    'SWIFT_EMIT_LOC_STRINGS' => 'YES',
  ))
  configure(app, 'CODE_SIGN_ENTITLEMENTS' => 'App/Feather.entitlements') if key == :macos
  app.add_file_references([app_swift])
  app.add_resources([assets])

  blocker = project.new_target(:app_extension, "Feather Blocker (#{p[:label]})", p[:sym], p[:deploy], nil, :swift, 'FeatherBlocker')
  configure(blocker, p[:settings].merge(
    'PRODUCT_NAME' => 'FeatherBlocker',
    'PRODUCT_BUNDLE_IDENTIFIER' => "#{BUNDLE_PREFIX}.blocker",
    'INFOPLIST_FILE' => 'ContentBlocker/Info.plist',
    'LD_RUNPATH_SEARCH_PATHS' => p[:ext_rpath],
    'SKIP_INSTALL' => 'YES',
  ))
  configure(blocker, 'CODE_SIGN_ENTITLEMENTS' => 'ContentBlocker/FeatherBlocker.entitlements') if key == :macos
  blocker.add_file_references([blocker_swift])
  blocker.add_resources([blocker_json])

  skipper = project.new_target(:app_extension, "Feather Skipper (#{p[:label]})", p[:sym], p[:deploy], nil, :swift, 'FeatherSkipper')
  configure(skipper, p[:settings].merge(
    'PRODUCT_NAME' => 'FeatherSkipper',
    'PRODUCT_BUNDLE_IDENTIFIER' => "#{BUNDLE_PREFIX}.skipper",
    'INFOPLIST_FILE' => 'Skipper/Info.plist',
    'LD_RUNPATH_SEARCH_PATHS' => p[:ext_rpath],
    'SKIP_INSTALL' => 'YES',
  ))
  configure(skipper, 'CODE_SIGN_ENTITLEMENTS' => 'Skipper/FeatherSkipper.entitlements') if key == :macos
  skipper.add_file_references([skipper_swift])
  skipper.add_resources(skipper_resources)

  # Embed both extensions in the app.
  embed = app.new_copy_files_build_phase('Embed App Extensions')
  embed.dst_subfolder_spec = Xcodeproj::Constants::COPY_FILES_BUILD_PHASE_DESTINATIONS[:plug_ins]
  embed.dst_path = ''
  [blocker, skipper].each do |ext|
    app.add_dependency(ext)
    build_file = embed.add_file_reference(ext.product_reference)
    build_file.settings = { 'ATTRIBUTES' => ['RemoveHeadersOnCopy'] }
  end

  scheme = Xcodeproj::XCScheme.new
  scheme.add_build_target(app)
  scheme.set_launch_target(app)
  scheme.save_as(PROJECT_PATH, "Feather (#{p[:label]})", true)
end

# Xcodeproj pins Cocoa/Foundation references to one SDK version, which shows
# as a missing file on any other Xcode. Swift auto-links them, so drop them.
project.targets.each { |t| t.frameworks_build_phase.clear }
project.files.select { |f| f.last_known_file_type == 'wrapper.framework' }.each(&:remove_from_project)
project.main_group.groups.select { |g| g.display_name == 'Frameworks' && g.empty? }.each(&:remove_from_project)

project.save

puts "wrote #{PROJECT_PATH.sub(ROOT + '/', '')}"
project.targets.each do |t|
  phases = t.build_phases.map { |ph| "#{ph.display_name}(#{ph.files.count})" }.join(', ')
  puts "  #{t.name}: #{t.product_type.split('.').last} -> #{t.product_reference.path}; #{phases}"
end
