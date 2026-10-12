extends RefCounted

func to_cell(world_position: Vector2, cell_size: float) -> Vector2i:
	return Vector2i(roundi(world_position.x / cell_size), roundi(world_position.y / cell_size))
