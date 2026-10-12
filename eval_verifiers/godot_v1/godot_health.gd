extends SceneTree

func _initialize() -> void:
	var health_script = load("res://scripts/health.gd")
	if health_script == null:
		quit(1)
		return
	var health = health_script.new(10)
	if health.maximum != 10 or health.current != 10:
		quit(2)
		return
	health.damage(4)
	if health.current != 6:
		quit(3)
		return
	health.damage(100)
	if health.current != 0:
		quit(4)
		return
	health.heal(3)
	health.heal(100)
	if health.current != 10:
		quit(5)
		return
	health.damage(-2)
	health.heal(-2)
	if health.current != 10:
		quit(6)
		return
	var empty_health = health_script.new(-5)
	if empty_health.maximum != 0 or empty_health.current != 0:
		quit(7)
		return
	print("EVAL_PASS")
	quit(0)
