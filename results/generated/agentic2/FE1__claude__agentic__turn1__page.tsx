'use client';

import * as React from 'react';
import Grid from '@mui/material/Unstable_Grid2';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';

import { Budget } from '@/components/dashboard/overview/budget';
import { TotalCustomers } from '@/components/dashboard/overview/total-customers';
import { TasksProgress } from '@/components/dashboard/overview/tasks-progress';
import { TotalProfit } from '@/components/dashboard/overview/total-profit';
import { Sales } from '@/components/dashboard/overview/sales';
import { Traffic } from '@/components/dashboard/overview/traffic';
import { LatestProducts } from '@/components/dashboard/overview/latest-products';
import { LatestOrders } from '@/components/dashboard/overview/latest-orders';
import { apiRequest } from '@/lib/api-client';

interface DashboardSummary {
  budget?: string;
  budgetTrend?: string;
  totalCustomers?: number;
  customersTrend?: string;
  tasksProgress?: number;
  totalProfit?: string;
  salesData?: {
    labels: string[];
    datasets: {
      name: string;
      data: number[];
    }[];
  };
  trafficData?: {
    labels: string[];
    datasets: number[];
  };
  recentProducts?: any[];
  recentTransactions?: any[];
}

export default function DashboardPage(): React.JSX.Element {
  const [summary, setSummary] = React.useState<DashboardSummary | null>(null);
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let isMounted = true;

    async function fetchSummary() {
      try {
        setLoading(true);
        setError(null);
        const data = await apiRequest('/dashboard/summary');
        if (isMounted) {
          setSummary(data ?? {});
        }
      } catch (err: any) {
        if (isMounted) {
          if (err.message === 'BACKEND_OFFLINE') {
            setError('Unable to connect to the server. Please try again later.');
          } else {
            setError(err.message || 'Failed to load dashboard data.');
          }
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchSummary();

    return () => {
      isMounted = false;
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

  const recentProducts = summary?.recentProducts ?? [];
  const recentTransactions = summary?.recentTransactions ?? [];

  return (
    <Box
      component="main"
      sx={{
        flexGrow: 1,
        py: 4,
        px: { xs: 2, md: 3 },
      }}
    >
      <Typography variant="h4" sx={{ mb: 3 }}>
        Dashboard
      </Typography>

      <Grid container spacing={3}>
        {/* KPI Cards */}
        <Grid xs={12} sm={6} lg={3}>
          <Budget
            diff={summary?.budgetTrend ? Number(summary.budgetTrend) : undefined}
            trend={summary?.budgetTrend && Number(summary.budgetTrend) >= 0 ? 'up' : 'down'}
            sx={{ height: '100%' }}
            value={summary?.budget ?? '$0'}
          />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TotalCustomers
            diff={summary?.customersTrend ? Number(summary.customersTrend) : undefined}
            trend={summary?.customersTrend && Number(summary.customersTrend) >= 0 ? 'up' : 'down'}
            sx={{ height: '100%' }}
            value={summary?.totalCustomers !== undefined ? String(summary.totalCustomers) : '0'}
          />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TasksProgress
            sx={{ height: '100%' }}
            value={summary?.tasksProgress ?? 0}
          />
        </Grid>

        <Grid xs={12} sm={6} lg={3}>
          <TotalProfit
            sx={{ height: '100%' }}
            value={summary?.totalProfit ?? '$0'}
          />
        </Grid>

        {/* Charts */}
        <Grid xs={12} lg={8}>
          <Sales
            chartSeries={
              summary?.salesData?.datasets?.map((ds) => ({
                name: ds.name,
                data: ds.data,
              })) ?? [
                { name: 'This year', data: [] },
                { name: 'Last year', data: [] },
              ]
            }
            sx={{ height: '100%' }}
          />
        </Grid>

        <Grid xs={12} lg={4}>
          <Traffic
            chartSeries={summary?.trafficData?.datasets ?? []}
            labels={summary?.trafficData?.labels ?? []}
            sx={{ height: '100%' }}
          />
        </Grid>

        {/* Tables */}
        <Grid xs={12} md={6}>
          <LatestProducts
            products={recentProducts}
            sx={{ height: '100%' }}
          />
        </Grid>

        <Grid xs={12} md={6}>
          <LatestOrders
            orders={recentTransactions}
            sx={{ height: '100%' }}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
