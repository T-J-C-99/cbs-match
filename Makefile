up:
	docker compose up --build

down:
	docker compose down

seed:
	python api/scripts/seed.py --n-users $${N:-100} --reset

test:
	cd api && pytest -q

match:
	curl -s -X POST http://localhost:8000/admin/matches/run-weekly -H "X-Admin-Token: dev-admin-token"
