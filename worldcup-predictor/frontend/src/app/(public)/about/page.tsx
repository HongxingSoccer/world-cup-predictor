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
            世界杯预测平台，覆盖每场比赛的 1x2 概率、比分矩阵、过/小球、双方进球，以及赔率价值（EV）信号。
          </p>
          <p>
            模型训练数据涵盖近 10 年国际赛 + 主流联赛的 xG、Elo、阵容、伤停、近期状态等
            28 维特征。每场比赛在开球前 24 小时内重新计算，结果通过 MLflow 版本化追踪。
          </p>
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-100">方法论</h2>
        </CardHeader>
        <CardBody className="space-y-3 text-sm leading-relaxed text-slate-300">
          <p>
            主模型为 Poisson GLM + Elo 协变量，相比纯 Poisson 准确率提升 ~7
            个百分点，并在 Brier 校准上同步提升。比分矩阵保留 Dixon-Coles 修正，对低分对决（0-0 / 0-1 / 1-0 / 1-1）的偏差更友好。
          </p>
          <p>
            所有预测结果一经生成即不可变，结算后写入<a className="text-brand-400 hover:underline" href="/track-record">战绩追踪</a>页面，对外公开命中率 / ROI / 连红记录。
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
