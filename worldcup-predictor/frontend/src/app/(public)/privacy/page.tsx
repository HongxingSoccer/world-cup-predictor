import type { Metadata } from 'next';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';

export const metadata: Metadata = {
  title: '隐私政策',
  description: 'WCP · 世界杯预测的隐私政策。',
};

export default function PrivacyPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-100">隐私政策</h1>
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-100">我们收集的信息</h2>
        </CardHeader>
        <CardBody className="space-y-3 text-sm leading-relaxed text-slate-300">
          <p>
            注册账号时收集手机号或邮箱用于身份识别，订阅时收集支付渠道（支付宝 /
            微信支付）必要的订单信息。所有 API 通信使用 HTTPS 加密。
          </p>
          <p>
            浏览行为（点击、收藏、推送已读）以匿名化形式聚合，用于改进推送频次与排序模型，不会与第三方共享原始记录。
          </p>
          <p>
            用户可随时在 <a className="text-brand-400 hover:underline" href="/profile">个人中心</a>{' '}
            注销账号；注销后保留必要的财务凭证 30 天，其余字段立即清除。
          </p>
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-100">Cookie 与本地存储</h2>
        </CardHeader>
        <CardBody className="space-y-3 text-sm leading-relaxed text-slate-300">
          <p>
            本网站仅使用必要的 Cookie 维持登录状态与订阅权限缓存，不投放第三方广告或跟踪 Cookie。
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
