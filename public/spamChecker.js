/**
 * KINGMAILER SpamChecker v2.0
 * Real-time spam score analysis — no external API, runs in browser
 * Modelled after SpamAssassin rules + Gmail / Outlook / Yahoo / iCloud / Hotmail signals
 */

// ── Keyword scoring lists ─────────────────────────────────────────────────────
const SC_SUBJECT = [
    { words: ['urgent', 'action required', 'respond immediately', 'respond now', 'open immediately'], pts: 10 },
    { words: ['click here', 'click now', 'act now', 'act immediately', 'don\'t miss', 'open now'], pts: 10 },
    { words: ['free money', 'earn money', 'make money', 'guaranteed income', 'work from home'], pts: 9 },
    { words: ['winner', 'won the', 'you\'ve been selected', 'congratulations you', 'you are the winner'], pts: 9 },
    { words: ['account suspended', 'account blocked', 'account compromised', 'unusual activity', 'verify your account'], pts: 8 },
    { words: ['invoice', 'billing statement', 'your bill', 'payment due', 'past due'], pts: 7 },
    { words: ['shipment', 'shipped', 'package delivered', 'delivery failed', 'delivery notification'], pts: 6 },
    { words: ['order confirmation', 'order info', 'order update', 'purchase confirmation'], pts: 5 },
    { words: ['free', 'limited offer', 'exclusive deal', 'limited time', 'expires soon'], pts: 5 },
    { words: ['dear customer', 'dear user', 'dear member', 'dear friend', 'valued customer'], pts: 7 },
    { words: ['paypal', 'fedex', 'ups', 'dhl fedex', 'irs refund', 'amazon gift'], pts: 7 },
    { words: ['confirm your', 'verify your', 'validate your', 'update your information'], pts: 6 },
    { words: ['prize', 'reward', 'gift card', 'gift voucher'], pts: 6 },
    { words: ['password', 'login credentials', 'sign in required'], pts: 5 },
];

const SC_BODY = [
    { words: ['click here', 'click below', 'click this link'], pts: 9 },
    { words: ['this is not spam', 'not a spam', 'not spam'], pts: 10 },  // ironic
    { words: ['to be removed', 'to unsubscribe', 'to opt out', 'remove from list'], pts: 4 },
    { words: ['100% free', 'absolutely free', 'completely free', 'for free!!!'], pts: 9 },
    { words: ['no credit card required', 'risk-free trial', 'money back guarantee'], pts: 6 },
    { words: ['you have been selected', 'you are a winner', 'you won'], pts: 9 },
    { words: ['limited time offer', 'act now before', 'expires in 24', 'don\'t delay'], pts: 7 },
    { words: ['lowest price', 'best price guaranteed', 'unbeatable price'], pts: 5 },
    { words: ['weight loss', 'diet pills', 'male enhancement', 'pharmacy online'], pts: 9 },
    { words: ['casino', 'gambling', 'jackpot winner', 'lottery result'], pts: 9 },
    { words: ['earn $', 'make $', 'profit $', 'daily income'], pts: 7 },
    { words: ['buy now', 'order now', 'shop now', 'purchase now'], pts: 4 },
    { words: ['once in a lifetime', 'once-in-a-lifetime', 'never seen before'], pts: 6 },
    { words: ['as seen on tv', 'as seen on cnn', 'featured on bbc'], pts: 5 },
];

// ── Provider definitions ──────────────────────────────────────────────────────
const SC_PROVIDERS = [
    {
        id: 'gmail', name: 'Gmail', icon: '📧',
        w: { sub: 1.4, body: 1.2, links: 1.4, caps: 1.1, imageOnly: 1.6, noText: 1.3, spintax: 0.7 },
        inbox: 30, promo: 60, hasPromo: true,
    },
    {
        id: 'outlook', name: 'Outlook', icon: '📨',
        w: { sub: 1.5, body: 1.1, links: 1.0, caps: 1.3, imageOnly: 1.2, noText: 1.1, spintax: 0.75 },
        inbox: 35, promo: 65, hasPromo: false,
    },
    {
        id: 'yahoo', name: 'Yahoo Mail', icon: '🟣',
        w: { sub: 1.2, body: 1.3, links: 1.2, caps: 1.0, imageOnly: 1.1, noText: 1.0, spintax: 0.8 },
        inbox: 40, promo: 68, hasPromo: false,
    },
    {
        id: 'icloud', name: 'iCloud Mail', icon: '🍎',
        w: { sub: 1.1, body: 1.1, links: 1.1, caps: 0.9, imageOnly: 1.0, noText: 1.0, spintax: 0.8 },
        inbox: 38, promo: 65, hasPromo: false,
    },
    {
        id: 'hotmail', name: 'Hotmail', icon: '🔵',
        w: { sub: 1.3, body: 1.0, links: 1.0, caps: 1.1, imageOnly: 1.2, noText: 1.0, spintax: 0.75 },
        inbox: 35, promo: 62, hasPromo: true,
    },
];

// ── HTML → plain text ─────────────────────────────────────────────────────────
function _scPlain(html) {
    return (html || '')
        .replace(/<style[\s\S]*?<\/style>/gi, '')
        .replace(/<script[\s\S]*?<\/script>/gi, '')
        .replace(/<br\s*\/?>/gi, ' ')
        .replace(/<\/?(p|div|li|h[1-6]|td|tr)[^>]*>/gi, ' ')
        .replace(/<[^>]+>/g, '')
        .replace(/&nbsp;/gi, ' ').replace(/&amp;/gi, '&')
        .replace(/&lt;/gi, '<').replace(/&gt;/gi, '>')
        .replace(/\s+/g, ' ').trim();
}

// ── Score subject keywords ────────────────────────────────────────────────────
function _scoreKeywords(text, list) {
    const low = (text || '').toLowerCase();
    const hits = [];
    let pts = 0;
    for (const group of list) {
        for (const w of group.words) {
            if (low.includes(w)) {
                pts += group.pts;
                hits.push({ word: w, pts: group.pts });
                break; // one match per group
            }
        }
    }
    return { pts, hits };
}

// ── Main analysis ─────────────────────────────────────────────────────────────
function analyzeSpam(subject, bodyHtml) {
    subject = subject || '';
    bodyHtml = bodyHtml || '';

    const issues = [];      // { type:'warn'|'good'|'tip', msg }
    const factors = {};      // raw factor values

    // ── Subject scoring ──────────────────────────────────────────────────────
    const subK = _scoreKeywords(subject, SC_SUBJECT);
    factors.subKeywords = subK.pts;
    subK.hits.forEach(h => issues.push({ type: 'warn', msg: `Subject: "${h.word}" is a known spam trigger (+${h.pts}pts)` }));

    // ALL CAPS ratio in subject
    const subAlpha = subject.replace(/[^a-zA-Z]/g, '');
    const subCaps = subject.replace(/[^A-Z]/g, '');
    const capsRatio = subAlpha.length > 3 ? subCaps.length / subAlpha.length : 0;
    factors.subCaps = capsRatio > 0.55 ? 12 : capsRatio > 0.35 ? 6 : 0;
    if (factors.subCaps >= 6) issues.push({ type: 'warn', msg: `Subject: ${Math.round(capsRatio * 100)}% ALL CAPS — looks like shouting (+${factors.subCaps}pts)` });

    // Exclamation marks in subject
    const exclSub = (subject.match(/!/g) || []).length;
    factors.subExcl = exclSub >= 3 ? exclSub * 3 : exclSub >= 2 ? 4 : 0;
    if (factors.subExcl > 0) issues.push({ type: 'warn', msg: `Subject: ${exclSub} exclamation mark(s) — spam signal (+${factors.subExcl}pts)` });

    // Spintax in subject (good!)
    const subSpintax = subject.includes('{') && subject.includes('|');
    factors.subSpintax = subSpintax ? 1 : 0;
    if (subSpintax) issues.push({ type: 'good', msg: 'Subject: Spintax detected — email content varies per recipient ✅' });

    // ── Body scoring ─────────────────────────────────────────────────────────
    const bodyText = _scPlain(bodyHtml);
    const bodyLow = bodyText.toLowerCase();

    const bodyK = _scoreKeywords(bodyText, SC_BODY);
    factors.bodyKeywords = bodyK.pts;
    bodyK.hits.forEach(h => issues.push({ type: 'warn', msg: `Body: "${h.word}" found — spam trigger (+${h.pts}pts)` }));

    // Link density
    const links = (bodyHtml.match(/<a[\s\S]*?href/gi) || []).length;
    factors.links = links > 6 ? 18 : links > 4 ? 12 : links > 2 ? 6 : 0;
    if (links > 4) issues.push({ type: 'warn', msg: `Body: ${links} hyperlinks (>4 is a bulk-mail signal, +${factors.links}pts)` });
    else if (links > 2) issues.push({ type: 'warn', msg: `Body: ${links} hyperlinks (>2 slightly increases spam score, +${factors.links}pts)` });

    // ALL CAPS words in body
    const capsWords = (bodyText.match(/\b[A-Z]{4,}\b/g) || [])
        .filter(w => !['HTML', 'MIME', 'HTTP', 'HTTPS', 'SMTP', 'IMAP', 'NOTE', 'INFO', 'DKIM', 'SPF'].includes(w));
    factors.bodyCaps = Math.min(capsWords.length * 2, 14);
    if (capsWords.length > 2) issues.push({ type: 'warn', msg: `Body: ${capsWords.length} ALL-CAPS words (${capsWords.slice(0, 3).join(', ')}…) +${factors.bodyCaps}pts` });

    // Exclamation abuse in body
    const exclBody = (bodyText.match(/!/g) || []).length;
    factors.bodyExcl = exclBody > 5 ? 8 : exclBody > 3 ? 4 : 0;
    if (factors.bodyExcl > 0) issues.push({ type: 'warn', msg: `Body: ${exclBody} exclamation marks — overuse looks promotional (+${factors.bodyExcl}pts)` });

    // Image-only detection
    const imgCount = (bodyHtml.match(/<img/gi) || []).length;
    const textLen = bodyText.length;
    const isImgOnly = imgCount > 0 && textLen < 60;
    factors.imageOnly = isImgOnly ? 22 : 0;
    if (isImgOnly) issues.push({ type: 'warn', msg: 'Body: Image-only email with almost no text — very high spam risk (+22pts)' });

    // Low text-to-HTML ratio (not image-only but still very heavy HTML)
    const htmlLen = bodyHtml.length;
    const ratio = htmlLen > 0 ? textLen / htmlLen : 1;
    factors.lowText = (!isImgOnly && ratio < 0.08 && htmlLen > 200) ? 8 : 0;
    if (factors.lowText > 0) issues.push({ type: 'warn', msg: `Body: Very low text-to-HTML ratio (${Math.round(ratio * 100)}%) — spam template fingerprint (+8pts)` });

    // Spintax in body (good!)
    const bodySpintax = bodyHtml.includes('{') && bodyHtml.includes('|');
    factors.bodySpintax = bodySpintax ? 1 : 0;
    if (bodySpintax) issues.push({ type: 'good', msg: 'Body: Spintax detected — content varies per recipient ✅' });

    // ── Tips ─────────────────────────────────────────────────────────────────
    const hasWarnings = issues.some(i => i.type === 'warn');
    if (hasWarnings && !subSpintax && !bodySpintax) {
        issues.push({ type: 'tip', msg: 'Tip: Use spintax {Hello|Hi|Hey} {$recipientName|there} in subject/body to uniquify each email' });
    }
    if (subK.pts > 10 && subSpintax) {
        issues.push({ type: 'tip', msg: 'Tip: Move spam keywords inside spintax options e.g. {Your package|It} is {shipped|on the way}' });
    }
    if (links > 3) {
        issues.push({ type: 'tip', msg: 'Tip: Reduce link count to 1–2 max. Spam filters count every <a href>.' });
    }
    if (!hasWarnings && !isImgOnly) {
        issues.push({ type: 'good', msg: 'No major spam triggers detected in subject or body ✅' });
    }

    // ── Per-provider scoring ──────────────────────────────────────────────────
    const results = SC_PROVIDERS.map(p => {
        const w = p.w;

        // Base score before provider weighting
        let raw = 0;
        raw += factors.subKeywords * w.sub;
        raw += factors.subCaps * w.caps;
        raw += factors.subExcl * w.caps;
        raw += factors.bodyKeywords * w.body;
        raw += factors.links * w.links;
        raw += factors.bodyCaps * w.caps;
        raw += factors.bodyExcl * w.body;
        raw += factors.imageOnly * w.imageOnly;
        raw += factors.lowText * w.noText;

        // Spintax reduces score (good)
        if (factors.subSpintax) raw *= w.spintax;
        if (factors.bodySpintax) raw *= w.spintax;

        const score = Math.min(100, Math.max(0, Math.round(raw)));

        let verdict, colour, vicon;
        if (score < p.inbox) {
            verdict = 'Inbox'; colour = '#22c55e'; vicon = '🟢';
        } else if (p.hasPromo && score < p.promo) {
            verdict = 'Promotions Tab'; colour = '#f59e0b'; vicon = '🟡';
        } else if (!p.hasPromo && score < p.promo) {
            verdict = 'Junk / Promotions'; colour = '#f59e0b'; vicon = '🟡';
        } else {
            verdict = 'Spam'; colour = '#ef4444'; vicon = '🔴';
        }

        return { ...p, score, verdict, colour, vicon };
    });

    // Overall verdict (worst of all providers)
    const worst = results.reduce((a, b) => a.score > b.score ? a : b);

    return { results, issues, factors, worst };
}

// Expose globally
window.analyzeSpam = analyzeSpam;
window.scPlain = _scPlain;
