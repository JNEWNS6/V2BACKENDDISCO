import fetch from 'node-fetch';
import cheerio from 'cheerio';

export async function scrapeBootsPromos(){
  const url = 'https://www.boots.com/coupons';
  const resp = await fetch(url);
  const html = await resp.text();
  const $ = cheerio.load(html);
  const promos = [];
  $('.coupon-tile').each((_, el) => {
    const code = $(el).find('.coupon-code').text().trim();
    const desc = $(el).find('.coupon-desc').text().trim();
    const discount = parseInt(desc.match(/(\d+)%/)?.[1] || '0', 10);
    if (code) promos.push({ code, discount_percent: discount||null, description: desc||null, expires: null });
  });
  return promos;
}