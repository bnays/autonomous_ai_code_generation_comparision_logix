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
  budget?: string | number;
  totalCustomers?: string | number;
  tasksProgress?: number;
  totalProfit?: string | number;
  sales?: {
    chartSeries?: unknown[];
    labels?: string[];
    [key: string]: unknown;
  };
  traffic?: {
    chartSeries?: number[];
    labels?: string[];
    [key: string]: unknown;
  };
  recentProducts?: unknown[];
  recentTransactions?: unknown[];
  [key: string]: unknown;
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
      } catch (err: unknown) {
        if (!cancelled) {
          if (err instanceof Error) {
            if (err.message === 'BACKEND_OFFLINE') {
              setError('Unable to reach the server. Please try again later.');
            } else {
              setError(err.message || 'Failed to load dashboard data.');
            }
          } else {
            setError('An unexpected error occurred.');
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

  const data: DashboardSummary = summary ?? {};

  const recentProducts: unknown[] = Array.isArray(data.recentProducts) ? data.recentProducts : [];
  const recentTransactions: unknown[] = Array.isArray(data.recentTransactions)
    ? data.recentTransactions
    : [];

  const salesChartSeries = data.sales?.chartSeries ?? [];
  const salesLabels = data.sales?.labels ?? [];

  const trafficChartSeries = data.traffic?.chartSeries ?? [];
  const trafficLabels = data.traffic?.labels ?? [];

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Dashboard
      </Typography>

      <Grid container spacing={3}>
        {/* KPI Cards */}
        <Grid xs={12} sm={6} lg={3}>
          <Budget
            diff={12}
            trend="up"
            sx={{ height: '100%' }}
            value={
              data.budget !== undefined
                ? String(data.budget)
                : '$0'
            }
          />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TotalCustomers
            diff={16}
            trend="down"
            sx={{ height: '100%' }}
            value={
              data.totalCustomers !== undefined
                ? String(data.totalCustomers)
                : '0'
            }
          />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TasksProgress
            sx={{ height: '100%' }}
            value={
              typeof data.tasksProgress === 'number'
                ? data.tasksProgress
                : 0
            }
          />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TotalProfit
            sx={{ height: '100%' }}
            value={
              data.totalProfit !== undefined
                ? String(data.totalProfit)
                : '$0'
            }
          />
        </Grid>

        {/* Charts */}
        <Grid xs={12} lg={8}>
          <Sales
            chartSeries={salesChartSeries as { name: string; data: number[] }[]}
            labels={salesLabels as string[]}
            sx={{ height: '100%' }}
          />
        </Grid>

        <Grid xs={12} lg={4}>
          <Traffic
            chartSeries={trafficChartSeries as number[]}
            labels={trafficLabels as string[]}
            sx={{ height: '100%' }}
          />
        </Grid>

        {/* Tables */}
        <Grid xs={12} md={6}>
          <LatestProducts
            products={recentProducts as Parameters<typeof LatestProducts>[0]['products']}
            sx={{ height: '100%' }}
          />
        </Grid>

        <Grid xs={12} md={6}>
          <LatestOrders
            orders={recentTransactions as Parameters<typeof LatestOrders>[0]['orders']}
            sx={{ height: '100%' }}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
