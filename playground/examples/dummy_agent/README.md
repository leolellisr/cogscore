# DummyAgentLearning

Example CogScore architecture bundle with a `/learning/act` endpoint.

The endpoint uses online tabular Q-learning to select a proportional-control
gain. The Q-table survives across episodes during one experiment and is reset
when CogScore calls `/reset` for a new learning run.

Build and run locally:

```bash
docker build -t dummy-agent-learning .
docker run --rm -p 9000:9000 dummy-agent-learning
```

Health check:

```bash
curl http://localhost:9000/health
```
