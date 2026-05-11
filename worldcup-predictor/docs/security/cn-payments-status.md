# CN payment channels (Alipay / WeChat Pay) — security status

> **TL;DR.** Disabled by default in any environment that boots with the
> production profile. The Stripe channel is unaffected and works
> normally. To re-enable Alipay / WeChat you MUST replace the stub
> signature verifier with the real SDK call first; see the checklist
> at the bottom of this document.

## What's currently shipped

`PaymentService.verifySignature(channel, payload)` is a Phase-3 stub:

```java
private boolean verifySignature(String channel, JsonNode payload) {
    // TODO(Phase 3.5): implement Alipay RSA2 / WeChat HMAC-SHA256 checks.
    return payload != null && !payload.isEmpty();
}
```

In other words **any non-empty JSON body is treated as a valid signed
callback**. With the endpoint reachable from the public internet, an
attacker who knows or guesses a merchant `out_trade_no` can craft a
single POST that flips a Payment row from `pending` to `paid` — and
because `PaymentService.handleCallback` then calls
`SubscriptionService.activateSubscription`, the attacker also grants
the corresponding user a paid subscription window.

## The lockdown (Phase 2)

Two layers, both controlled by `wcp.payments.enable-cn-channels`:

1. **Order-creation path** — `PaymentService.initPayment` throws
   `PaymentChannelDisabledException` (HTTP 503) for an alipay /
   wechat_pay channel when the flag is off. No DB write happens, so
   even if an attacker tries to create a `pending` row first they
   can't.
2. **Callback endpoint** — `POST /api/v1/payments/callback/{alipay,wechat_pay}`
   returns a plain HTTP 404 when the flag is off. We chose 404 over
   503 so naïve probes can't tell the endpoint exists, minimising the
   public attack surface.

The Stripe path (`POST /api/v1/payments/callback/stripe`) is unaffected
— it uses the real `Stripe.Webhook.constructEvent` HMAC check and a
real Checkout Session creation API call.

## Per-environment defaults

| Profile | `wcp.payments.enable-cn-channels` | Notes |
|---|---|---|
| `prod` (no override) | **false** | hard-wired safe default in `application.yml` |
| `dev` (`application-dev.yml`) | true | local docker-compose stack |
| `test` (`application-test.yml`) | true | so integration tests keep covering the control flow |
| EKS staging / production helm | **false** | will be set explicitly via `WCP_ENABLE_CN_PAYMENTS=false` |

Override via env var: `WCP_ENABLE_CN_PAYMENTS=true` (only do this in
isolated environments where the endpoint is not internet-reachable, or
once the SDK swap below is complete).

## Re-enabling checklist (when integrating the real SDKs)

Each item is a blocker — do **not** flip the flag to `true` in a
public environment until every box is checked.

- [ ] **Replace `verifySignature` with the real SDK call**:
  - Alipay: `AlipayClient.execute()` over the callback params, or
    `AlipaySignature.rsaCheckV1(params, alipayPublicKey, "UTF-8",
    "RSA2")`.
  - WeChat: V3 API HMAC-SHA256 verify against the merchant API V3 key
    (with the `Wechatpay-Signature`, `Wechatpay-Timestamp`,
    `Wechatpay-Nonce` headers from the request).
- [ ] **Replace `initPayment` stub-marker payload** with the real SDK
  response:
  - Alipay: `trade.app.pay` returns a signed `orderInfo` string.
  - WeChat: `unifiedorder` returns a `prepay_id` + signed launch params.
- [ ] **Persist the merchant signing key + private key per environment**
  in AWS Secrets Manager (NOT in `.env` or compose). Bind to a K8s
  Secret + mount path the application reads at boot.
- [ ] **Idempotency** is already enforced (Payment.status==paid is a
  no-op). Verify the new SDK path keeps that.
- [ ] **Amount tampering guard** is already enforced
  (`extractAmountCny` vs `payment.amountCny`). Verify under SDK responses.
- [ ] **End-to-end smoke test in a sandbox**:
  - Alipay sandbox merchant account
  - WeChat sandbox (Pay Test Mode)
- [ ] **Logging audit** — confirm the SDK exceptions don't leak the
  merchant private key into application logs.
- [ ] **Rotate the merchant keys** in production within 24h of the
  first real transaction (Alipay / WeChat dashboards both support this).

Only after all of the above can `WCP_ENABLE_CN_PAYMENTS=true` be safely
set in the production helm values.
