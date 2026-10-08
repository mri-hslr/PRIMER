# Experiment Log

## Prototype issue found
The earlier app recalculated mastery from the CSV on every answer request.

## Consequence
The submitted answer was not persisted into the current learner state, so
repeated correct answers appeared to stop changing mastery.

## Fix
Historical CSV → initialise session state once → update session state after
each response.

## Next
Replace the in-memory state with PostgreSQL when backend integration begins.
