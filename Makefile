.PHONY: rules test project diagrams icons build clean

# Compile rules/*.txt into the JSON Safari loads.
rules:
	python3 tools/build_rules.py

# Redraw the README figures in docs/ from the compiled rule list.
diagrams: rules
	python3 tools/gen_diagrams.py

# Render the app icon set (needs: pip install pillow).
icons:
	python3 tools/gen_icons.py

# Validate the compiled list and the YouTube skipper (needs node + playwright).
test: rules
	python3 tools/test_rules.py
	node tools/test_skipper.mjs

# Regenerate Feather.xcodeproj (needs: gem install xcodeproj).
project:
	ruby tools/gen_project.rb

# Build the app and both extensions with Xcode's command-line tools (macOS only).
build: rules
	xcodebuild -project Feather.xcodeproj -scheme Feather -configuration Release \
		-derivedDataPath build build

clean:
	rm -rf build
