import type { Metadata } from 'next';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';

export const metadata: Metadata = {
  title: '服务条款',
  description: 'WCP · 世界杯预测的服务条款与免责声明。',
};

export default function TermsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-100">服务条款</h1>
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-100">免责声明</h2>
        </CardHeader>
        <CardBody className="space-y-3 text-sm leading-relaxed text-slate-300">
          <p>
            WCP 提供的所有比赛预测、概率分布、价值信号均为基于历史数据的统计参考，<strong className="text-slate-100">不构成任何形式的投资或下注建议</strong>。
          </p>
          <p>
            用户应自行判断风险，理性观赛。本平台不对任何因使用本服务造成的直接或间接损失承担责任。
          </p>
          <p>
            订阅服务一经开通自动生效；订阅期内可随时取消，已支付费用不予退还（除中国大陆法律明确规定的情形外）。
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
