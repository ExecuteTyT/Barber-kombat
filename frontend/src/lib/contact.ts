/** Helpers for contacting a client from review/admin screens. */

/**
 * Reduce a phone to digits only (no '+'). A leading Russian trunk '8' on an
 * 11-digit number is normalised to '7'. Returns '' when there aren't enough
 * digits to be a real number.
 */
export function phoneDigits(phone: string | null | undefined): string {
  if (!phone) return ''
  let d = phone.replace(/\D/g, '')
  if (d.length === 11 && d.startsWith('8')) d = '7' + d.slice(1)
  return d.length >= 10 ? d : ''
}

/** wa.me deep link with an optional pre-filled message, or null if no phone. */
export function waLink(phone: string | null | undefined, text?: string): string | null {
  const d = phoneDigits(phone)
  if (!d) return null
  const q = text && text.trim() ? `?text=${encodeURIComponent(text.trim())}` : ''
  return `https://wa.me/${d}${q}`
}

/** tel: link, or null if no usable phone. */
export function telLink(phone: string | null | undefined): string | null {
  const d = phoneDigits(phone)
  if (!d) return null
  return `tel:+${d}`
}
