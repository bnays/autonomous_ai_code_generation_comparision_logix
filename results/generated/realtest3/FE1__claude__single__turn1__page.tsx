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
  totalCustomers?: string | number;
  tasksProgress?: number;
  totalProfit?: string | number;
  salesData?: unknown;
  trafficData?: unknown;
  trafficLabels?: string[];
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
        <Typography color="text.secondary">Loading dashboard…</Typography>
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
        px: { xs: 2, md: 4 },
      }}
    >
      <Typography variant="h4" sx={{ mb: 4 }}>
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
            value={
              typeof summary?.tasksProgress === 'number'
                ? summary.tasksProgress
                : 0
            }
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

        {/* Charts */}
        <Grid xs={12} lg={8}>
          <Sales
            chartSeries={
              Array.isArray(summary?.salesData)
                ? (summary!.salesData as { name: string; data: number[] }[])
                : [
                    {
                      name: 'This year',
                      data: [18, 16, 5, 8, 3, 14, 14, 16, 17, 19, 18, 20],
                    },
                    {
                      name: 'Last year',
                      data: [12, 11, 4, 6, 2, 9, 9, 10, 11, 12, 13, 13],
                    },
                  ]
            }
            sx={{ height: '100%' }}
          />
        </Grid>

        <Grid xs={12} lg={4}>
          <Traffic
            chartSeries={
              Array.isArray(summary?.trafficData)
                ? (summary!.trafficData as number[])
                : [63, 15, 22]
            }
            labels={
              Array.isArray(summary?.trafficLabels)
                ? (summary!.trafficLabels as string[])
                : ['Desktop', 'Tablet', 'Phone']
            }
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
