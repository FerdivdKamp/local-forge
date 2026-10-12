extends SceneTree

func _initialize() -> void:
	var grid_script = load("res://scripts/grid.gd")
	if grid_script == null:
		quit(1)
		return
	var grid = grid_script.new()
	if grid.to_cell(Vector2(0, 0), 16.0) != Vector2i(0, 0):
		quit(2)
		return
	if grid.to_cell(Vector2(31, 15), 16.0) != Vector2i(1, 0):
		quit(3)
		return
	if grid.to_cell(Vector2(-1, 0), 16.0) != Vector2i(-1, 0):
		quit(4)
		return
	if grid.to_cell(Vector2(-17, -16), 16.0) != Vector2i(-2, -1):
		quit(5)
		return
	print("EVAL_PASS")
	quit(0)
