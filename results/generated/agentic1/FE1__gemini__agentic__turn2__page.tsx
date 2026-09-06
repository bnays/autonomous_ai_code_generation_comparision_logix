'use client';

import { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import CircularProgress from '@mui/material/CircularProgress';
import Grid from '@mui/material/Grid';
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
  sales?: any;
  traffic?: any;
  recentProducts?: any[];
  recentTransactions?: any[];
  latestProducts?: any[];
  latestOrders?: any[];
  [key: string]: any;
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    async function fetchDashboardSummary() {
      try {
        setIsLoading(true);
        const data = await apiRequest('/dashboard/summary');
        if (isMounted && data) {
          setSummary(data);
        }
      } catch (error) {
        console.error('Failed to fetch dashboard summary:', error);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    fetchDashboardSummary();

    return () => {
      isMounted = false;
    };
  }, []);

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '60vh',
          width: '100%',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  const recentProducts = Array.isArray(summary?.recentProducts)
    ? summary.recentProducts
    : Array.isArray(summary?.latestProducts)
    ? summary.latestProducts
    : [];

  const recentTransactions = Array.isArray(summary?.recentTransactions)
    ? summary.recentTransactions
    : Array.isArray(summary?.latestOrders)
    ? summary.latestOrders
    : [];

  return (
    <Box
      component="main"
      sx={{
        flexGrow: 1,
        py: 4,
      }}
    >
      <Container maxWidth="xl">
        <Grid container spacing={3}>
          <Grid item lg={3} sm={6} xs={12}>
            <Budget
              difference={12}
              trend="up"
              sx={{ height: '100%' }}
              value={summary?.budget ?? '$24k'}
            />
          </Grid>
          <Grid item lg={3} sm={6} xs={12}>
            <TotalCustomers
              difference={16}
              trend="down"
              sx={{ height: '100%' }}
              value={summary?.totalCustomers ?? '1.6k'}
            />
          </Grid>
          <Grid item lg={3} sm={6} xs={12}>
            <TasksProgress
              sx={{ height: '100%' }}
              value={summary?.tasksProgress ?? 75.5}
            />
          </Grid>
          <Grid item lg={3} sm={6} xs={12}>
            <TotalProfit
              sx={{ height: '100%' }}
              value={summary?.totalProfit ?? '$15k'}
            />
          </Grid>

          <Grid item lg={8} xs={12}>
            <Sales
              chartSeries={
                summary?.sales?.chartSeries ??
                summary?.sales ?? [
                  { name: 'This year', data: [18, 16, 5, 8, 3, 14, 14, 16, 12, 12, 18, 18] },
                  { name: 'Last year', data: [12, 11, 4, 6, 2, 9, 9, 10, 11, 12, 13, 13] },
                ]
              }
              sx={{ height: '100%' }}
            />
          </Grid>
          <Grid item lg={4} md={6} xs={12}>
            <Traffic
              chartSeries={summary?.traffic?.chartSeries ?? summary?.traffic ?? [63, 15, 22]}
              labels={summary?.traffic?.labels ?? ['Desktop', 'Tablet', 'Phone']}
              sx={{ height: '100%' }}
            />
          </Grid>

          <Grid item lg={4} md={6} xs={12}>
            <LatestProducts products={recentProducts} sx={{ height: '100%' }} />
          </Grid>
          <Grid item lg={8} md={12} xs={12}>
            <LatestOrders orders={recentTransactions} sx={{ height: '100%' }} />
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
}
