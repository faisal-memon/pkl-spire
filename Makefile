PKL ?= pkl
DOCKER ?= docker
CONFIG ?= examples/compose.pkl
OUT ?= out
VERSION ?= 0.1.0

.PHONY: render test validate
render:
	$(PKL) eval -m $(OUT) $(CONFIG)

test:
	python3 -m unittest discover -s tests -v

validate: render test
	$(DOCKER) compose -f $(OUT)/server.compose.yaml config -q
	$(DOCKER) compose -f $(OUT)/agent.compose.yaml config -q

.PHONY: package
package:
	PKL_PACKAGE_VERSION="$(VERSION)" $(PKL) project package --output-path dist
