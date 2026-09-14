.PHONY: test generate run app demo

test:
	pytest -q

generate:
	python -m trajectory_gym.cli generate

run:
	python -m trajectory_gym.cli run $(ARGS)

app:
	streamlit run app/streamlit_app.py

demo:
	python -m trajectory_gym.cli demo $(ARGS)
