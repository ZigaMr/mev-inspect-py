from typing import List, Optional

from mev_inspect.schemas.classified_traces import (
    ClassifiedTrace,
    Classification,
)
from mev_inspect.schemas.swaps import Swap
from mev_inspect.schemas.transfers import ERC20Transfer
from mev_inspect.traces import get_traces_by_transaction_hash
from mev_inspect.transfers import (
    get_child_transfers,
    filter_transfers,
    remove_child_transfers_of_transfers,
)


def get_swaps(traces: List[ClassifiedTrace]) -> List[Swap]:
    swaps = []

    for _, transaction_traces in get_traces_by_transaction_hash(traces).items():
        swaps += _get_swaps_for_transaction(list(transaction_traces))

    return swaps


def _get_swaps_for_transaction(traces: List[ClassifiedTrace]) -> List[Swap]:
    ordered_traces = list(sorted(traces, key=lambda t: t.trace_address))

    swaps: List[Swap] = []
    prior_transfers: List[ERC20Transfer] = []

    for trace in ordered_traces:
        if trace.classification == Classification.transfer:
            prior_transfers.append(ERC20Transfer.from_trace(trace))

        elif trace.classification == Classification.swap:
            child_transfers = get_child_transfers(
                trace.transaction_hash,
                trace.trace_address,
                traces,
            )

            swap = _parse_swap(
                trace,
                remove_child_transfers_of_transfers(prior_transfers),
                remove_child_transfers_of_transfers(child_transfers),
            )

            if swap is not None:
                swaps.append(swap)

    return swaps


def _parse_swap(
    trace: ClassifiedTrace,
    prior_transfers: List[ERC20Transfer],
    child_transfers: List[ERC20Transfer],
) -> Optional[Swap]:
    pool_address = trace.to_address

    transfers_to_pool = filter_transfers(prior_transfers, to_address=pool_address)

    if len(transfers_to_pool) == 0:
        transfers_to_pool = filter_transfers(child_transfers, to_address=pool_address)

    if len(transfers_to_pool) == 0:
        raise RuntimeError("Expected at least one transfer to pool")

    transfers_from_pool = filter_transfers(child_transfers, from_address=pool_address)

    if len(transfers_from_pool) != 1:
        raise RuntimeError("Expected exactly one transfer from pool")

    transfer_in = transfers_to_pool[-1]
    transfer_out = transfers_from_pool[0]

    return Swap(
        abi_name=trace.abi_name,
        transaction_hash=trace.transaction_hash,
        block_number=trace.block_number,
        trace_address=trace.trace_address,
        pool_address=pool_address,
        from_address=transfer_in.from_address,
        to_address=transfer_out.to_address,
        token_in_address=transfer_in.token_address,
        token_in_amount=transfer_in.amount,
        token_out_address=transfer_out.token_address,
        token_out_amount=transfer_out.amount,
        error=trace.error,
    )
