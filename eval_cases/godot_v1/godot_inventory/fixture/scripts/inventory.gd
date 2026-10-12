extends RefCounted

func total_weight(items: Array[Dictionary]) -> int:
	var result := 0
	for item in items:
		result += int(item.get("weight", 0))
	return result
