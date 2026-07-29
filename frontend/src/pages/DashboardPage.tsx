import { IconBox, IconClipboardCheck, IconClockHour4 } from "@tabler/icons-react";

import { useAssets } from "../features/assets/api";

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  icon: typeof IconBox;
}) {
  return (
    <div className="col-sm-6 col-lg-4">
      <div className="card card-sm">
        <div className="card-body">
          <div className="row align-items-center">
            <div className="col-auto">
              <span className="bg-primary text-white avatar">
                <Icon size={24} />
              </span>
            </div>
            <div className="col">
              <div className="font-weight-medium">{value}</div>
              <div className="text-secondary">{label}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data } = useAssets();
  const total = data?.count ?? 0;

  return (
    <>
      <div className="page-header">
        <h2 className="page-title">Dashboard</h2>
      </div>
      <div className="row row-cards mt-1">
        <StatCard label="Bens cadastrados" value={total} icon={IconBox} />
        <StatCard label="Cautelas atrasadas" value="—" icon={IconClockHour4} />
        <StatCard label="Divergências (inventário)" value="—" icon={IconClipboardCheck} />
      </div>
    </>
  );
}
