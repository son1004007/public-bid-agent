"""문서 구조 및 표 검증 계약.
목적: DEF-03 표 블록/셀 범위·중첩, 각주 앵커 참조, 블록 계층 순환 방지 등 도메인 불변조건을 검증한다.
경계: ORM 외부에서 메모리 객체 또는 모델 인스턴스 검증을 수행하며 DB 트랜잭션과 독립적이다.
부작용: 불변조건 위반 시 ValidationError 발생. 상태 변경 없음.
실패: 구조적 모순 탐지 시 구체적 필드와 오류 사유 반환.
관련: docs/server-migration/17-domain-and-postgresql-contract.md §8.3 및 A25.
"""
from django.core.exceptions import ValidationError


def validate_table_grid(row_count: int, column_count: int, cells: list[dict]) -> dict:
    """표 격자 범위, 병합 셀 경계 및 중첩 여부를 검증한다.

    입력:
        row_count: 양의 정수 행 수
        column_count: 양의 정수 열 수
        cells: [
            {
                "cell_id": str,
                "row_index": int,
                "column_index": int,
                "rowspan": int (default 1),
                "colspan": int (default 1),
                "text": str,
                ...
            }
        ]
    반환:
        점유 격자 맵 {"grid": 2차원 리스트, "occupied_slots": int, "total_slots": int}
    예외:
        ValidationError: 범위 초과, 중첩, 음수 인덱스, 0 이하 span 발견 시
    """
    if row_count <= 0 or column_count <= 0:
        raise ValidationError(f"행 수({row_count}) 및 열 수({column_count})는 양의 정수여야 합니다.")

    grid = [[None for _ in range(column_count)] for _ in range(row_count)]
    seen_cell_ids = set()

    for idx, cell in enumerate(cells):
        cell_id = cell.get("cell_id") or f"cell_{idx}"
        if cell_id in seen_cell_ids:
            raise ValidationError(f"중복된 셀 ID가 표 내에 존재합니다: {cell_id}")
        seen_cell_ids.add(cell_id)

        r = cell.get("row_index")
        c = cell.get("column_index")
        rowspan = cell.get("rowspan", 1)
        colspan = cell.get("colspan", 1)

        if r is None or c is None:
            raise ValidationError(f"셀 {cell_id}에 row_index 또는 column_index가 누락되었습니다.")
        if r < 0 or c < 0:
            raise ValidationError(f"셀 {cell_id}의 좌표는 음수일 수 없습니다: ({r}, {c})")
        if rowspan < 1 or colspan < 1:
            raise ValidationError(f"셀 {cell_id}의 rowspan({rowspan}) 및 colspan({colspan})은 1 이상이어야 합니다.")

        if r + rowspan > row_count:
            raise ValidationError(
                f"셀 {cell_id}의 행 범위({r}~{r + rowspan})가 표 행 수({row_count})를 초과합니다."
            )
        if c + colspan > column_count:
            raise ValidationError(
                f"셀 {cell_id}의 열 범위({c}~{c + colspan})가 표 열 수({column_count})를 초과합니다."
            )

        for ri in range(r, r + rowspan):
            for ci in range(c, c + colspan):
                existing = grid[ri][ci]
                if existing is not None:
                    raise ValidationError(
                        f"셀 중첩 발견: 좌표 ({ri}, {ci})에 {existing}와 {cell_id}가 동시에 점유합니다."
                    )
                grid[ri][ci] = cell_id

    occupied = sum(1 for row in grid for slot in row if slot is not None)
    return {
        "grid": grid,
        "occupied_slots": occupied,
        "total_slots": row_count * column_count,
    }


def validate_block_hierarchy(blocks: list) -> None:
    """문서 블록 간 부모 참조가 동일 구조 소속이며 순환 참조가 없는지 검증한다."""
    block_map = {}
    for block in blocks:
        bid = getattr(block, "block_id", None) or block.get("block_id")
        block_map[bid] = block

    for bid, block in block_map.items():
        parent_id = getattr(block, "parent_block_id", None)
        if parent_id is None and isinstance(block, dict):
            parent_id = block.get("parent_block_id")

        visited = {bid}
        curr = parent_id
        while curr:
            if curr not in block_map:
                raise ValidationError(f"부모 블록 {curr}이 동일 구조 내에 존재하지 않습니다.")
            if curr in visited:
                raise ValidationError(f"블록 계층에 순환 참조가 발견되었습니다: {bid} -> {curr}")
            visited.add(curr)
            curr_block = block_map[curr]
            curr = getattr(curr_block, "parent_block_id", None)
            if curr is None and isinstance(curr_block, dict):
                curr = curr_block.get("parent_block_id")


def validate_footnote_anchors(footnote_block, available_block_ids: set[str]) -> None:
    """각주의 anchor_refs가 동일 구조 내 실재하는 블록/셀 ID만 참조하는지 검증한다."""
    anchor_refs = getattr(footnote_block, "anchor_refs", None)
    if anchor_refs is None and isinstance(footnote_block, dict):
        anchor_refs = footnote_block.get("anchor_refs", [])

    for anchor in anchor_refs:
        if anchor not in available_block_ids:
            raise ValidationError(
                f"각주 앵커 참조 {anchor}가 동일 문서 구조 내에 존재하지 않습니다."
            )
