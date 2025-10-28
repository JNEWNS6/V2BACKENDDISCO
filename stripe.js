import Stripe from 'stripe';
export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY, { apiVersion: '2024-06-20' });

export function successUrl(offerId){
  return (process.env.STRIPE_SUCCESS_URL || 'https://example.com/thanks?offer={OFFER_ID}').replace('{OFFER_ID}', encodeURIComponent(offerId));
}
export function cancelUrl(offerId){
  return (process.env.STRIPE_CANCEL_URL || 'https://example.com/cancel?offer={OFFER_ID}').replace('{OFFER_ID}', encodeURIComponent(offerId));
}