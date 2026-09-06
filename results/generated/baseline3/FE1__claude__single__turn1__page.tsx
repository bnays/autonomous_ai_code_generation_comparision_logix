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
  budget?: string | number;
  totalCustomers?: number;
  tasksProgress?: number;
  totalProfit?: string | number;
  sales?: {
    labels?: string[];
    datasets?: { name?: string; data?: number[] }[];
  };
  traffic?: {
    labels?: string[];
    datasets?: { data?: number[] }[];
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

  const recentProducts: unknown[] = summary?.recentProducts ?? [];
  const recentTransactions: unknown[] = summary?.recentTransactions ?? [];

  return (
    <Box
      component="main"
      sx={{
        flexGrow: 1,
        py: 3,
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
            diff={12}
            trend="up"
            sx={{ height: '100%' }}
            value={
              summary?.budget !== undefined
                ? String(summary.budget)
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
              summary?.totalCustomers !== undefined
                ? String(summary.totalCustomers)
                : '0'
            }
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
            value={
              summary?.totalProfit !== undefined
                ? String(summary.totalProfit)
                : '$0'
            }
          />
        </Grid>

        {/* Sales Chart */}
        <Grid xs={12} lg={8}>
          <Sales
            chartSeries={
              summary?.sales?.datasets?.map((ds) => ({
                name: ds.name ?? 'Series',
                data: ds.data ?? [],
              })) ?? [
                { name: 'This year', data: [] },
                { name: 'Last year', data: [] },
              ]
            }
            labels={
              summary?.sales?.labels ?? [
                'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
              ]
            }
            sx={{ height: '100%' }}
          />
        </Grid>

        {/* Traffic Chart */}
        <Grid xs={12} lg={4}>
          <Traffic
            chartSeries={summary?.traffic?.datasets?.[0]?.data ?? [63, 15, 22]}
            labels={summary?.traffic?.labels ?? ['Desktop', 'Tablet', 'Phone']}
            sx={{ height: '100%' }}
          />
        </Grid>

        {/* Latest Products */}
        <Grid xs={12} md={6} lg={4}>
          <LatestProducts
            products={recentProducts as any}
            sx={{ height: '100%' }}
          />
        </Grid>

        {/* Latest Orders */}
        <Grid xs={12} md={6} lg={8}>
          <LatestOrders
            orders={recentTransactions as any}
            sx={{ height: '100%' }}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
