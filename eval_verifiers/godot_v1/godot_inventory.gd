extends SceneTree

func _initialize() -> void:
	var inventory_script = load("res://scripts/inventory.gd")
	if inventory_script == null:
		quit(1)
		return
	var inventory = inventory_script.new()
	var empty: Array[Dictionary] = []
	if inventory.total_weight(empty) != 0:
		quit(2)
		return
	var items: Array[Dictionary] = [
		{"weight": 2, "quantity": 3},
		{"weight": 4},
	]
	if inventory.total_weight(items) != 10:
		quit(3)
		return
	var skipped: Array[Dictionary] = [
		{"weight": 99, "quantity": 0},
		{"weight": 20, "quantity": -2},
		{"weight": 5, "quantity": 2},
	]
	if inventory.total_weight(skipped) != 10:
		quit(4)
		return
	print("EVAL_PASS")
	quit(0)
