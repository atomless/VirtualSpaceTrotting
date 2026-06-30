.PHONY: help setup test test-unit test-site test-runtime test-code-quality test-mpulse-profiles test-mpulse-admin test-mpulse-cli test-mpulse-host content-corpus preview-imagery site-build build-runtime build bundle prepare-linode-host deploy-linode-one-shot remote-use remote-update remote-status remote-logs remote-start remote-stop remote-open-site remote-install-mpulse-admin remote-mpulse-list remote-mpulse-current remote-mpulse-verify

.DEFAULT_GOAL := help

PYTHON ?= python3
ENV_LOCAL ?= .env.local
VST_LOCAL_STATE_DIR ?= .vst
REMOTE_RECEIPTS_DIR ?= $(VST_LOCAL_STATE_DIR)/remotes
BUNDLE_DIR ?= $(VST_LOCAL_STATE_DIR)/bundles
PREPARE_LINODE_ARGS ?=
DEPLOY_LINODE_ARGS ?=
REMOTE ?=
MPULSE_REGISTRY_FILE ?=
MPULSE_PROFILE ?=

help:
	@printf '%s\n' 'VirtualSpaceTrotting commands:'
	@printf '%s\n' '  make setup                 Prepare local gitignored state.'
	@printf '%s\n' '  make test                  Run the focused helper test suite.'
	@printf '%s\n' '  make test-code-quality     Compile Python helper code.'
	@printf '%s\n' '  make build                 Generate content/imagery and build SvelteKit plus Rust runtime.'
	@printf '%s\n' '  make bundle                Build a committed-HEAD release bundle.'
	@printf '%s\n' '  make prepare-linode-host   Create/attach Linode host and write remote receipt.'
	@printf '%s\n' '  make deploy-linode-one-shot Create/attach Linode and install the Spin service.'
	@printf '%s\n' '  make remote-use REMOTE=x   Select a remote receipt.'
	@printf '%s\n' '  make remote-update         Ship committed HEAD to the selected remote.'
	@printf '%s\n' '  make remote-install-mpulse-admin MPULSE_REGISTRY_FILE=x MPULSE_PROFILE=x'
	@printf '%s\n' '  make remote-mpulse-list|remote-mpulse-current|remote-mpulse-verify'
	@printf '%s\n' '  make remote-status|remote-logs|remote-start|remote-stop|remote-open-site'

setup:
	@mkdir -p "$(VST_LOCAL_STATE_DIR)" "$(REMOTE_RECEIPTS_DIR)" "$(BUNDLE_DIR)"
	@touch "$(ENV_LOCAL)"
	@chmod 600 "$(ENV_LOCAL)"
	pnpm --dir site install
	@printf '%s\n' 'Local state prepared.'

test: test-unit test-site test-runtime

test-unit:
	$(PYTHON) -m unittest discover -s scripts/tests -p 'test_*.py'

test-site:
	pnpm --dir site test

test-runtime:
	cargo test

test-code-quality:
	$(PYTHON) -m compileall -q scripts

test-mpulse-profiles:
	$(PYTHON) -m unittest scripts.tests.test_mpulse_profiles -v

test-mpulse-admin:
	$(PYTHON) -m unittest scripts.tests.test_vst_mpulse_admin -v

test-mpulse-cli:
	$(PYTHON) -m unittest scripts.tests.test_vst_mpulse -v

test-mpulse-host:
	$(PYTHON) -m unittest scripts.tests.test_mpulse_host_setup -v

content-corpus:
	$(PYTHON) scripts/generate_location_corpus.py

preview-imagery: content-corpus
	$(PYTHON) scripts/generate_preview_imagery.py

site-build: preview-imagery
	pnpm --dir site install --frozen-lockfile
	pnpm --dir site build
	$(PYTHON) scripts/verify_static_output.py

build-runtime:
	cargo rustc --target wasm32-wasip1 --release --lib --crate-type cdylib
	@mkdir -p dist/wasm
	@cp target/wasm32-wasip1/release/virtual_space_trotting.wasm dist/wasm/virtual_space_trotting.wasm

build: site-build build-runtime

bundle:
	@mkdir -p "$(BUNDLE_DIR)"
	$(PYTHON) scripts/deploy/build_release_bundle.py \
		--repo-root "$(CURDIR)" \
		--archive-output "$(BUNDLE_DIR)/virtual-space-trotting-release.tar.gz" \
		--metadata-output "$(BUNDLE_DIR)/virtual-space-trotting-release.json"

prepare-linode-host: setup
	$(PYTHON) scripts/deploy/linode_host_setup.py \
		--env-file "$(ENV_LOCAL)" \
		--remote-receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		$(PREPARE_LINODE_ARGS)

deploy-linode-one-shot: setup
	$(PYTHON) scripts/deploy/linode_one_shot.py \
		--env-file "$(ENV_LOCAL)" \
		--remote-receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		$(DEPLOY_LINODE_ARGS)

remote-use:
	@test -n "$(REMOTE)" || (printf '%s\n' 'REMOTE=<name> is required.' >&2; exit 2)
	$(PYTHON) scripts/deploy/remote_target.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		use --name "$(REMOTE)"

remote-update:
	$(PYTHON) scripts/deploy/remote_target.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		update $(if $(REMOTE),--name "$(REMOTE)",)

remote-status:
	$(PYTHON) scripts/deploy/remote_target.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		status $(if $(REMOTE),--name "$(REMOTE)",)

remote-logs:
	$(PYTHON) scripts/deploy/remote_target.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		logs $(if $(REMOTE),--name "$(REMOTE)",)

remote-start:
	$(PYTHON) scripts/deploy/remote_target.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		start $(if $(REMOTE),--name "$(REMOTE)",)

remote-stop:
	$(PYTHON) scripts/deploy/remote_target.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		stop $(if $(REMOTE),--name "$(REMOTE)",)

remote-open-site:
	$(PYTHON) scripts/deploy/remote_target.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		open-site $(if $(REMOTE),--name "$(REMOTE)",)

remote-install-mpulse-admin:
	@test -n "$(MPULSE_REGISTRY_FILE)" || (printf '%s\n' 'MPULSE_REGISTRY_FILE=<path> is required.' >&2; exit 2)
	@test -n "$(MPULSE_PROFILE)" || (printf '%s\n' 'MPULSE_PROFILE=<name> is required.' >&2; exit 2)
	$(PYTHON) scripts/deploy/mpulse_host_setup.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		$(if $(REMOTE),--name "$(REMOTE)",) \
		install --registry-file "$(MPULSE_REGISTRY_FILE)" --initial-profile "$(MPULSE_PROFILE)"

remote-mpulse-list:
	$(PYTHON) scripts/deploy/mpulse_host_setup.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		$(if $(REMOTE),--name "$(REMOTE)",) list

remote-mpulse-current:
	$(PYTHON) scripts/deploy/mpulse_host_setup.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		$(if $(REMOTE),--name "$(REMOTE)",) current

remote-mpulse-verify:
	$(PYTHON) scripts/deploy/mpulse_host_setup.py \
		--env-file "$(ENV_LOCAL)" \
		--receipts-dir "$(REMOTE_RECEIPTS_DIR)" \
		$(if $(REMOTE),--name "$(REMOTE)",) verify
