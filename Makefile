export SHELL = sh
PACKAGE = lliuwin
ICON = data/images/lliuwin.ico
VERSION = 24.04
REVISION = 1
COPYRIGHTYEAR = 2009
AUTHOR = Agostino Russo
EMAIL = agostino.russo@gmail.com

all: build

build: lliuwin

lliuwin: lliuwin-pre-build
	PYTHONPATH=src tools/pywine -OO src/pypack/pypack --verbose --bytecompile --outputdir=build/wubi src/main.py build/data build/bin build/version.py build/winboot build/translations
	python3 build/pylauncher/pack.py build/wubi
	mv build/application.exe build/lliuwin.exe

lliuwinzip: lliuwin-pre-build
	PYTHONPATH=src tools/pywine src/pypack/pypack --verbose --outputdir=build/wubi src/main.py build/data build/bin build/version.py build/winboot build/translations
	cp wine/drive_c/Python27/python.exe build/wubi #TBD
	cd build; zip -r wubi.zip wubi

lliuwin-pre-build: check_wine pylauncher winboot2 src/main.py src/wubi/*.py cpuid version.py translations
	rm -rf build/wubi
	rm -rf build/bin
	mkdir -p build/bin
	rm -rf build/data
	mkdir -p build/data
	cp data/image.json data/isolist.ini build/data/
	cp -a data/images build/data/
	cp LICENSE AUTHORS build/data/
	cp wine/drive_c/windows/system32/python27.dll build/pylauncher
	cp build/cpuid/cpuid.dll build/bin

pot:
	xgettext --default-domain="$(PACKAGE)" --output="po/$(PACKAGE).pot" $(shell find src/wubi -name "*.py" | sort)
	sed -i 's/SOME DESCRIPTIVE TITLE/Translation template for $(PACKAGE)/' po/$(PACKAGE).pot
	sed -i "s/YEAR THE PACKAGE'S COPYRIGHT HOLDER/$(COPYRIGHTYEAR)/" po/$(PACKAGE).pot
	sed -i 's/FIRST AUTHOR <EMAIL@ADDRESS>, YEAR/$(AUTHOR) <$(EMAIL)>, $(COPYRIGHTYEAR)/' po/$(PACKAGE).pot
	sed -i 's/Report-Msgid-Bugs-To: /Report-Msgid-Bugs-To: $(EMAIL)/' po/$(PACKAGE).pot
	sed -i 's/CHARSET/UTF-8/' po/$(PACKAGE).pot
	sed -i 's/PACKAGE VERSION/$(VERSION)-r$(REVISION)/' po/$(PACKAGE).pot
	sed -i 's/PACKAGE/$(PACKAGE)/' po/$(PACKAGE).pot

update-po: pot
	for i in po/*.po ;\
	do \
	mv $$i $${i}.old ; \
	(msgmerge $${i}.old po/lliuwin.pot | msgattrib --no-obsolete > $$i) ; \
	rm $${i}.old ; \
	done

translations: po/*.po
	mkdir -p build/translations/
	@for po in $^; do \
		language=`basename $$po`; \
		language=$${language%%.po}; \
		target="build/translations/$$language/LC_MESSAGES"; \
		mkdir -p $$target; \
		msgfmt --output=$$target/$(PACKAGE).mo $$po; \
	done

version.py:
	$(shell mkdir -p build; echo 'version = "$(VERSION)"' > build/version.py)
	$(shell echo 'revision = $(REVISION)' >> build/version.py)
	$(shell echo 'application_name = "$(PACKAGE)"' >> build/version.py)

pylauncher: 7z src/pylauncher/*
	cp -rf src/pylauncher build
	cp "$(ICON)" build/pylauncher/application.ico
	sed -i 's/application_name/$(PACKAGE)/' build/pylauncher/pylauncher.exe.manifest
	cd build/pylauncher; make

cpuid: src/cpuid/cpuid.c
	cp -rf src/cpuid build
	cd build/cpuid; make

winboot2:
	mkdir -p build/winboot/EFI
	cp /usr/lib/grub/x86_64-efi-signed/gcdx64.efi.signed build/winboot/EFI/grubx64.efi
	cp /usr/lib/shim/shimx64.efi.signed build/winboot/EFI/shimx64.efi
	cp /usr/lib/shim/mmx64.efi build/winboot/EFI/mmx64.efi
	sbverify --list build/winboot/EFI/grubx64.efi
	sbverify --list build/winboot/EFI/shimx64.efi

winboot: grub4dos grubutil
	mkdir -p build/winboot
	cp -f data/menu.winboot build/winboot/menu.lst
	cp -f build/grub4dos/stage2/grldr build/winboot/wubildr
	cp -f build/grub4dos/stage2/grub.exe build/winboot/wubildr.exe
	dd if=build/winboot/wubildr of=build/winboot/wubildr.mbr bs=1 count=8192
	cd build/winboot; ../grubutil/grubinst/grubinst -o -b=wubildr wubildr.mbr

grub4dos: src/grub4dos/*
	cp -rf src/grub4dos build
	cd build/grub4dos;./configure --enable-preset-menu=../../data/menu.winboot
	cd build/grub4dos; make

grubutil: src/grubutil/grubinst/*
	cp -rf src/grubutil build
	cd build/grubutil/grubinst; make

# not compiling 7z at the moment, but source is used by pylauncher
7z: src/7z/C/*.c
	mkdir -p build/7z
	cp -rf src/7z build

runbin: lliuwin
	rm -rf build/test
	mkdir build/test
	cd build/test; ../../tools/wine ../lliuwin.exe --test

check_wine: tools/check_wine
	tools/check_wine

check_winboot: tools/check_winboot
	tools/check_winboot

unittest:
	tools/pywine tools/test

check: lliuwin
	tests/run

runpy:
	PYTHONPATH=src tools/pywine src/main.py --test

clean:
	rm -rf dist/*
	rm -rf build/*

distclean: clean
	rm -rf wine
	rm -rf tools/buildtest/*
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyc" -delete
	rm -rf .key
	rm -rf data/custom-installation/packages
	rm -rf shim

.PHONY: all build test lliuwin lliuwinzip lliuwin-pre-build pot runpy runbin check_wine check_winboot unittest
	7z translations version.py pylauncher winboot winboot2 grubutil grub4dos clean distclean
