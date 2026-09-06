'use client';

import * as React from 'react';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';

import { apiRequest } from '@/lib/api-client';
import { Budget } from '@/components/dashboard/overview/budget';
import { TotalCustomers } from '@/components/dashboard/overview/total-customers';
import { TasksProgress } from '@/components/dashboard/overview/tasks-progress';
import { TotalProfit } from '@/components/dashboard/overview/total-profit';
import { Sales } from '@/components/dashboard/overview/sales';
import { Traffic } from '@/components/dashboard/overview/traffic';
import { LatestProducts } from '@/components/dashboard/overview/latest-products';
import { LatestOrders } from '@/components/dashboard/overview/latest-orders';

interface TrafficData {
  labels?: string[];
  series?: number[];
}

interface DashboardSummary {
  budget?: string | number;
  totalCustomers?: string | number;
  tasksProgress?: number;
  totalProfit?: string | number;
  salesData?: unknown;
  trafficData?: TrafficData;
  recentProducts?: unknown[];
  recentTransactions?: unknown[];
}

export default function DashboardPage(): React.JSX.Element {
  const [summary, setSummary] = React.useState<DashboardSummary | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    async function fetchSummary() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiRequest('/dashboard/summary');
        if (!cancelled) {
          setSummary(data ?? {});
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err?.message ?? 'Failed to load dashboard data.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchSummary();

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        <CircularProgress />
        <Typography variant="body2" color="text.secondary">
          Loading dashboard…
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
          flexDirection: 'column',
          gap: 1,
        }}
      >
        <Typography variant="h6" color="error">
          Unable to load dashboard
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {error}
        </Typography>
      </Box>
    );
  }

  const {
    budget,
    totalCustomers,
    tasksProgress,
    totalProfit,
    salesData,
    trafficData,
    recentProducts,
    recentTransactions,
  } = summary ?? {};

  const safeRecentProducts = Array.isArray(recentProducts) ? recentProducts : [];
  const safeRecentTransactions = Array.isArray(recentTransactions) ? recentTransactions : [];

  // Traffic component expects chartSeries as a number array — guard against undefined
  const trafficSeries: number[] = Array.isArray(trafficData?.series)
    ? trafficData!.series!
    : [];
  const trafficLabels: string[] = Array.isArray(trafficData?.labels)
    ? trafficData!.labels!
    : [];

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, md: 3 } }}>
      <Grid container spacing={3}>
        {/* KPI Cards */}
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <Budget value={budget} />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <TotalCustomers value={totalCustomers} />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <TasksProgress value={tasksProgress} />
        </Grid>

        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <TotalProfit value={totalProfit} />
        </Grid>

        {/* Charts */}
        <Grid size={{ xs: 12, lg: 8 }}>
          <Sales data={salesData} />
        </Grid>

        <Grid size={{ xs: 12, lg: 4 }}>
          <Traffic chartSeries={trafficSeries} labels={trafficLabels} />
        </Grid>

        {/* Latest Products */}
        <Grid size={{ xs: 12, md: 6 }}>
          <LatestProducts products={safeRecentProducts} />
        </Grid>

        {/* Latest Orders */}
        <Grid size={{ xs: 12, md: 6 }}>
          <LatestOrders orders={safeRecentTransactions} />
        </Grid>
      </Grid>
    </Box>
  );
}
