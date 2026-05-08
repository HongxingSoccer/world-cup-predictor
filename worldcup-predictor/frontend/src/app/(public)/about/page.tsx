import type { Metadata } from 'next';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';

export const metadata: Metadata = {
  title: '关于 WCP',
  description: '关于 WCP · 世界杯预测的产品定位与方法论。',
};

export default function AboutPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-100">关于 WCP</h1>
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-100">产品定位</h2>
        </CardHeader>
        <CardBody className="space-y-3 text-sm leading-relaxed text-slate-300">
          <p>
            WCP（World Cup Predictor）是一个基于 AI 模型的 2026
            世界杯预测平台，覆盖每场比赛的胜平负概率、比分矩阵、大/小球、双方进球，并对照庄家赔率挑出值得下注的盘口。
          </p>
          <p>
            模型综合 28 项数据：射门质量、球队实力、阵容、伤停、近期状态等，训练样本来自近 10
            年国际赛 + 主流联赛。每场比赛在开球前 24 小时内重新计算，所有版本可追溯。
          </p>
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-100">方法论</h2>
        </CardHeader>
        <CardBody className="space-y-3 text-sm leading-relaxed text-slate-300">
          <p>
            模型基于进球分布 + 球队实力评分，比赛结果概率比单纯历史进球预测准确度提升约
            7 个百分点。比分矩阵针对低分对决（0-0 / 0-1 / 1-0 / 1-1）做了额外修正，更贴近真实分布。
          </p>
          <p>
            所有预测结果一经生成即不可变，结算后写入<a className="text-brand-400 hover:underline" href="/track-record">战绩追踪</a>页面，对外公开命中率、累计收益、连红记录。
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
