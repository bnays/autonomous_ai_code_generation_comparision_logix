'use client';

import * as React from 'react';
import Grid from '@mui/material/Unstable_Grid2';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';

import { apiRequest } from '@/lib/api-client';
import { Budget } from '@/components/dashboard/overview/budget';
import { TotalCustomers } from '@/components/dashboard/overview/total-customers';
import { TasksProgress } from '@/components/dashboard/overview/tasks-progress';
import { TotalProfit } from '@/components/dashboard/overview/total-profit';
import { Sales } from '@/components/dashboard/overview/sales';
import { Traffic } from '@/components/dashboard/overview/traffic';
import { LatestProducts } from '@/components/dashboard/overview/latest-products';
import { LatestOrders } from '@/components/dashboard/overview/latest-orders';

interface DashboardSummary {
  budget?: {
    value: string;
    diff?: number;
    trend?: 'up' | 'down';
  };
  totalCustomers?: {
    value: string;
    diff?: number;
    trend?: 'up' | 'down';
  };
  tasksProgress?: {
    value: number;
  };
  totalProfit?: {
    value: string;
  };
  sales?: {
    chartSeries: { name: string; data: number[] }[];
  };
  traffic?: {
    chartSeries: number[];
    labels: string[];
  };
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
          if (err?.message === 'BACKEND_OFFLINE') {
            setError('Unable to reach the server. Please check your connection and try again.');
          } else {
            setError(err?.message ?? 'Failed to load dashboard data.');
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void fetchSummary();

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
        <Typography color="text.secondary" variant="body2">
          Loading dashboard…
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  const data = summary ?? {};

  const recentProducts: unknown[] = Array.isArray(data.recentProducts) ? data.recentProducts : [];
  const recentTransactions: unknown[] = Array.isArray(data.recentTransactions) ? data.recentTransactions : [];

  return (
    <Box sx={{ flexGrow: 1, p: { xs: 2, md: 3 } }}>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Dashboard
      </Typography>

      <Grid container spacing={3}>
        {/* KPI Cards */}
        <Grid xs={12} sm={6} lg={3}>
          <Budget
            value={data.budget?.value ?? '$0'}
            diff={data.budget?.diff}
            trend={data.budget?.trend ?? 'up'}
            sx={{ height: '100%' }}
          />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TotalCustomers
            value={data.totalCustomers?.value ?? '0'}
            diff={data.totalCustomers?.diff}
            trend={data.totalCustomers?.trend ?? 'up'}
            sx={{ height: '100%' }}
          />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TasksProgress
            value={data.tasksProgress?.value ?? 0}
            sx={{ height: '100%' }}
          />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TotalProfit
            value={data.totalProfit?.value ?? '$0'}
            sx={{ height: '100%' }}
          />
        </Grid>

        {/* Charts */}
        <Grid xs={12} lg={8}>
          <Sales
            chartSeries={
              data.sales?.chartSeries ?? [
                { name: 'This year', data: [] },
                { name: 'Last year', data: [] },
              ]
            }
            sx={{ height: '100%' }}
          />
        </Grid>

        <Grid xs={12} lg={4}>
          <Traffic
            chartSeries={data.traffic?.chartSeries ?? []}
            labels={data.traffic?.labels ?? []}
            sx={{ height: '100%' }}
          />
        </Grid>

        {/* Tables */}
        <Grid xs={12} md={6}>
          <LatestProducts
            products={recentProducts as any}
            sx={{ height: '100%' }}
          />
        </Grid>

        <Grid xs={12} md={6}>
          <LatestOrders
            orders={recentTransactions as any}
            sx={{ height: '100%' }}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
