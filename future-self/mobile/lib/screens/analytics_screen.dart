import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../providers/nlp_provider.dart';
import '../services/nlp_service.dart';

class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen>
    with TickerProviderStateMixin {
  late final NlpProvider _nlpProvider;
  late final TabController _tabController;
  final SupabaseClient supabase = Supabase.instance.client;
  
  String _selectedTimeframe = '7d';
  final List<String> _timeframes = ['1d', '7d', '30d', '90d'];
  
  @override
  void initState() {
    super.initState();
    _nlpProvider = NlpProvider();
    _tabController = TabController(length: 3, vsync: this);
    _loadAnalytics();
  }
  
  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }
  
  Future<void> _loadAnalytics() async {
    final user = supabase.auth.currentUser;
    if (user != null) {
      await _nlpProvider.loadUserInsights(user.id, timeframe: _selectedTimeframe);
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Analytics'),
        actions: [
          // Timeframe Selector
          PopupMenuButton<String>(
            icon: const Icon(Icons.date_range),
            onSelected: (String timeframe) {
              setState(() {
                _selectedTimeframe = timeframe;
              });
              _loadAnalytics();
            },
            itemBuilder: (BuildContext context) {
              return _timeframes.map((String timeframe) {
                return PopupMenuItem<String>(
                  value: timeframe,
                  child: Row(
                    children: [
                      if (_selectedTimeframe == timeframe)
                        const Icon(Icons.check, size: 16),
                      if (_selectedTimeframe == timeframe)
                        const SizedBox(width: 8),
                      Text(_getTimeframeLabel(timeframe)),
                    ],
                  ),
                );
              }).toList();
            },
          ),
          // Refresh Button
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadAnalytics,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(icon: Icon(Icons.analytics), text: 'Overview'),
            Tab(icon: Icon(Icons.mood), text: 'Emotions'),
            Tab(icon: Icon(Icons.balance), text: 'Bias'),
          ],
        ),
      ),
      body: AnimatedBuilder(
        animation: _nlpProvider,
        builder: (context, child) {
          if (_nlpProvider.isAnyLoading) {
            return const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 16),
                  Text('Loading analytics...'),
                ],
              ),
            );
          }
          
          return TabBarView(
            controller: _tabController,
            children: [
              _buildOverviewTab(),
              _buildEmotionsTab(),
              _buildBiasTab(),
            ],
          );
        },
      ),
    );
  }
  
  Widget _buildOverviewTab() {
    final analytics = _nlpProvider.userAnalytics;
    final emotionSummary = _nlpProvider.getEmotionSummary();
    final biasSummary = _nlpProvider.getBiasSummary();
    
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Summary Cards
          Row(
            children: [
              Expanded(
                child: _buildSummaryCard(
                  'Messages',
                  analytics?.totalMessages.toString() ?? '0',
                  Icons.chat_bubble_outline,
                  Colors.blue,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildSummaryCard(
                  'Timeframe',
                  _getTimeframeLabel(_selectedTimeframe),
                  Icons.date_range,
                  Colors.green,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          
          // Emotion Summary
          if (!emotionSummary['isEmpty']) ...[
            _buildSectionHeader('Emotion Summary'),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          NlpService.getEmotionEmoji(emotionSummary['mostCommonEmotion']),
                          style: const TextStyle(fontSize: 24),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Most Common: ${emotionSummary['mostCommonEmotion']}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 16,
                                ),
                              ),
                              Text(
                                '${emotionSummary['mostCommonCount']} occurrences',
                                style: const TextStyle(color: Colors.grey),
                              ),
                            ],
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: Colors.blue[100],
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: Text(
                            '${emotionSummary['totalAnalyses']} analyzed',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Average Confidence: ${NlpService.formatEmotionScore(emotionSummary['averageConfidence'])}',
                      style: const TextStyle(color: Colors.grey),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
          ],
          
          // Bias Summary
          if (!biasSummary['isEmpty']) ...[
            _buildSectionHeader('Bias Summary'),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.balance, size: 24, color: Colors.orange),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Bias Score: ${NlpService.formatBiasScore(biasSummary['averageBiasScore'])}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 16,
                                ),
                              ),
                              Text(
                                '${biasSummary['totalBiasDetections']} biases detected',
                                style: const TextStyle(color: Colors.grey),
                              ),
                            ],
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: Colors.orange[100],
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: Text(
                            '${biasSummary['totalAnalyses']} analyzed',
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
          
          // Recent Activity
          const SizedBox(height: 16),
          _buildSectionHeader('Recent Activity'),
          if (_nlpProvider.recentEmotions.isNotEmpty) ...[
            const Text(
              'Recent Emotions',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            SizedBox(
              height: 100,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: _nlpProvider.recentEmotions.take(10).length,
                itemBuilder: (context, index) {
                  final emotion = _nlpProvider.recentEmotions[index];
                  return Container(
                    width: 80,
                    margin: const EdgeInsets.only(right: 8),
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(8.0),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              NlpService.getEmotionEmoji(emotion.primaryEmotion),
                              style: const TextStyle(fontSize: 20),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              emotion.primaryEmotion,
                              style: const TextStyle(fontSize: 10),
                              textAlign: TextAlign.center,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            Text(
                              NlpService.formatEmotionScore(emotion.confidence),
                              style: const TextStyle(
                                fontSize: 8,
                                color: Colors.grey,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ],
      ),
    );
  }
  
  Widget _buildEmotionsTab() {
    final emotionTrends = _nlpProvider.emotionTrends;
    
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionHeader('Emotion Trends'),
          
          if (emotionTrends != null) ...[
            // Average Scores
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Average Emotion Scores',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 12),
                    ...emotionTrends.averageScores.entries.map((entry) {
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4.0),
                        child: Row(
                          children: [
                            Text(
                              NlpService.getEmotionEmoji(entry.key),
                              style: const TextStyle(fontSize: 20),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                entry.key,
                                style: const TextStyle(fontWeight: FontWeight.w500),
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: Color(int.parse('0xFF${NlpService.getEmotionColor(entry.key).substring(1)}')),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                NlpService.formatEmotionScore(entry.value),
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    }),
                  ],
                ),
              ),
            ),
          ] else ...[
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16.0),
                child: Text(
                  'No emotion trends available for the selected timeframe.',
                  style: TextStyle(color: Colors.grey),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
  
  Widget _buildBiasTab() {
    final biasPatterns = _nlpProvider.biasPatterns;
    
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionHeader('Bias Patterns'),
          
          if (biasPatterns != null) ...[
            // Overall Trend
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Row(
                  children: [
                    const Icon(Icons.trending_up, size: 24),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Overall Bias Trend',
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                            ),
                          ),
                          Text(
                            biasPatterns.overallTrend > 0 
                                ? 'Increasing bias detected'
                                : biasPatterns.overallTrend < 0
                                    ? 'Decreasing bias detected'
                                    : 'Stable bias levels',
                            style: TextStyle(
                              color: biasPatterns.overallTrend > 0 
                                  ? Colors.red 
                                  : biasPatterns.overallTrend < 0
                                      ? Colors.green
                                      : Colors.grey,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: biasPatterns.overallTrend > 0 
                            ? Colors.red[100] 
                            : biasPatterns.overallTrend < 0
                                ? Colors.green[100]
                                : Colors.grey[100],
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Text(
                        '${biasPatterns.overallTrend.toStringAsFixed(1)}%',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            
            // Bias Patterns
            if (biasPatterns.patterns.isNotEmpty) ...[
              const Text(
                'Detected Bias Types',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 8),
              ...biasPatterns.patterns.map((pattern) {
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                pattern.type,
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 14,
                                ),
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: _getTrendColor(pattern.trend),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                pattern.trend.toUpperCase(),
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Text(
                              'Frequency: ${pattern.frequency}',
                              style: const TextStyle(color: Colors.grey),
                            ),
                            const SizedBox(width: 16),
                            Text(
                              'Confidence: ${NlpService.formatBiasScore(pattern.averageConfidence)}',
                              style: const TextStyle(color: Colors.grey),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              }),
            ],
            
            // Recommendations
            if (biasPatterns.recommendations.isNotEmpty) ...[
              const SizedBox(height: 16),
              _buildSectionHeader('Recommendations'),
              ...biasPatterns.recommendations.map((recommendation) {
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Row(
                      children: [
                        const Icon(Icons.lightbulb, color: Colors.amber),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(recommendation),
                        ),
                      ],
                    ),
                  ),
                );
              }),
            ],
          ] else ...[
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16.0),
                child: Text(
                  'No bias patterns available for the selected timeframe.',
                  style: TextStyle(color: Colors.grey),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
  
  Widget _buildSummaryCard(String title, String value, IconData icon, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 8),
            Text(
              value,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            Text(
              title,
              style: const TextStyle(
                color: Colors.grey,
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8.0),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
  
  String _getTimeframeLabel(String timeframe) {
    switch (timeframe) {
      case '1d':
        return 'Last 24 hours';
      case '7d':
        return 'Last 7 days';
      case '30d':
        return 'Last 30 days';
      case '90d':
        return 'Last 90 days';
      default:
        return timeframe;
    }
  }
  
  Color _getTrendColor(String trend) {
    switch (trend.toLowerCase()) {
      case 'increasing':
        return Colors.red;
      case 'decreasing':
        return Colors.green;
      case 'stable':
      default:
        return Colors.grey;
    }
  }
}