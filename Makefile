.PHONY: build
build:
	docker build -t paradex-bot .

.PHONY: run
run:
	docker run -it --rm --name paradex-bot -v ${PWD}:/paradex paradex-bot

.PHONY: stop
stop:
	docker stop paradex-bot
