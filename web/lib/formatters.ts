/**
 * Formats minor currency units (integers) safely.
 * e.g., 15000 minor units -> £150.00
 */
export function formatMoney(amountMinor: number, currency = 'GBP'): string {
  const amountMajor = amountMinor / 100;
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amountMajor);
}