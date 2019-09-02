SCHEMA_DIR = /usr/share/glib-2.0/schemas/
USER_PLUGIN_DIR = ~/.local/share/rhythmbox/plugins/
SYSTEM_PLUGIN_DIR = /usr/lib/rhythmbox/plugins/
SYSTEM_DATA_DIR = /usr/share/rhythmbox/plugins/
SYSTEM64_PLUGIN_DIR = /usr/lib64/rhythmbox/plugins/

install: schema
	@echo "Installing plugin files to $(USER_PLUGIN_DIR) ..."
	@mkdir -p $(USER_PLUGIN_DIR)
	@rm -r -f $(USER_PLUGIN_DIR)szyrics/
	@cp -r ./szyrics/ $(USER_PLUGIN_DIR)
	@echo "Done!"

install-systemwide: schema
	@if [ -d "$(SYSTEM_PLUGIN_DIR)rb" ]; then \
		echo "Installing plugin files to $(SYSTEM_PLUGIN_DIR) ..."; \
		sudo rm -r -f $(SYSTEM_PLUGIN_DIR)szyrics/; \
		sudo cp -r ./szyrics/ $(SYSTEM_PLUGIN_DIR); \
		sudo chmod -R 755 $(SYSTEM_PLUGIN_DIR)szyrics/; \
	else \
		echo "Installing plugin files to $(SYSTEM64_PLUGIN_DIR) ..."; \
		sudo rm -r -f $(SYSTEM64_PLUGIN_DIR)szyrics/; \
		sudo cp -r ./szyrics/ $(SYSTEM64_PLUGIN_DIR); \
		sudo chmod -R 755 $(SYSTEM64_PLUGIN_DIR)szyrics/; \
	fi
	@echo "Installing data files to $(SYSTEM_DATA_DIR) ..."
	@sudo rm -r -f $(SYSTEM_DATA_DIR)szyrics/
	@sudo  mkdir -p $(SYSTEM_DATA_DIR)szyrics/
	@sudo cp -r ./ui/ $(SYSTEM_DATA_DIR)szyrics/
	@sudo cp -r ./img/ $(SYSTEM_DATA_DIR)szyrics/
	@sudo chmod -R 755 $(SYSTEM_DATA_DIR)szyrics/
	@echo "Done!"

schema:
	@echo "Installing schema..."
	@sudo cp ./org.gnome.rhythmbox.plugins.szyrics.gschema.xml $(SCHEMA_DIR)
	@sudo glib-compile-schemas $(SCHEMA_DIR)
	@echo "... done!"

uninstall:
	@echo "Removing schema file..."
	@sudo rm -f $(SCHEMA_DIR)org.gnome.rhythmbox.plugins.szyrics.gschema.xml
	@echo "Removing plugin files..."
	@rm -r -f $(USER_PLUGIN_DIR)szyrics/
	@sudo rm -r -f $(SYSTEM_PLUGIN_DIR)szyrics/
	@sudo rm -r -f $(SYSTEM64_PLUGIN_DIR)szyrics/
	@echo "Done!"
	
update-po-files:
	@echo "Update *.po files..."
	@cd $(LOCALE_DIR); \
	for i in *.po; do \
		echo `basename $$i`; \
		lang=`basename $$i .po`; \
		intltool-update -g messages $$lang; \
	done