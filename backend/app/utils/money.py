from decimal import Decimal, ROUND_HALF_UP

TWO_DP = Decimal("0.01")
HUNDRED = Decimal("100")


def quantize_money(value: Decimal) -> Decimal:
    """Round monetary amounts to 2 decimal places using ROUND_HALF_UP."""
    return Decimal(value).quantize(TWO_DP, rounding=ROUND_HALF_UP)


def calculate_bill_discount(
    gross_amount: Decimal,
    discount_percentage: Decimal,
) -> tuple[Decimal, Decimal]:
    """Compute (discount_amount, net_amount) using Decimal arithmetic.

    Documented business rule:
    A new percentage discount replaces any previous discount on the bill's gross_amount:
        discount_amount = round_half_up(gross_amount * discount_percentage / 100, 2)
        net_amount = gross_amount - discount_amount
    """
    pct = Decimal(discount_percentage)
    if pct < Decimal("0") or pct > HUNDRED:
        raise ValueError("Discount percentage must be between 0 and 100")

    gross = quantize_money(Decimal(gross_amount))
    discount_amount = quantize_money((gross * pct) / HUNDRED)
    net_amount = quantize_money(gross - discount_amount)
    return discount_amount, net_amount

