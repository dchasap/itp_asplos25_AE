
#ifndef PRED_TABLE_H
#define PRED_TABLE_H

#include <stdlib.h>
#include <assert.h>
#include <stdio.h>
#include <iostream>
#include <string.h>
#include <math.h>

bool table_update_flag;

// this is used in the predTable, we should 
// translate this for ChampSim in init
typedef enum {
		L1icache = 0,
		L1dcache = 5,
		L2cache = 6,
		L3cache = 7,
		BTB = 1,
		L1iTLB = 2,
		L1dTLB = 4,
		TLB2 =3,
		indirBP = 9,
		BP = 8
}	cpu_structure;

uint64_t mix(uint64_t a, uint64_t b, uint64_t c) {
	a -= b; a -= c; a ^= (c >> 13);
	b -= c; b -= a; b ^= (a << 8);
	c -= a; c -= b; c ^= (b >> 13);
	a -= b; a -= c; a ^= (c >> 12);
	b -= c; b -= a; b ^= (a << 16);
	c -= a; c -= b; c ^= (b >> 5);
	a -= b; a -= c; a ^= (c >> 3);
	b -= c; b -= a; b ^= (a << 10);
	c -= a; c -= b; c ^= (b >> 15);
	return c;
}

uint64_t f1(uint64_t x) {
	uint64_t fone = mix(0xfeedface, 0xdeadb10c, x);
	return fone;
}

uint64_t f2(uint64_t x) {
	uint64_t ftwo = mix(0xc001d00d, 0xfade2b1c, x);
	return ftwo;
}

uint64_t fi(uint64_t x, int i) {
	uint64_t ind = (f1(x)) + (f2(x));
	return ind ;
}

struct predTable {
	public:
		int counter_max;
		int counter_min, counter_width = 2;
		int predictor_index_bits, predictor_table_entries, predictor_tables;
		int **tables;

		predTable(int pred_inx_bits, int pred_num_tables);
		uint64_t get_table_index(int type, uint64_t trace, int t);
		int get_prediction(int type, uint64_t trace);
		void block_is_dead(int type, uint64_t, bool);
		~predTable();
};

uint64_t predTable::get_table_index(int type, uint64_t trace, int t)
{
	uint64_t x1 ;
	x1 = fi(trace , t);
	uint64_t x2 = x1 & ((1 << predictor_index_bits)-1);
	//x2 = ( x2 & (1 << predictor_index_bits)-1);
	x2 = x2 & ((1 << predictor_index_bits)-1);
	return x2;
}

void predTable::block_is_dead(int type, uint64_t trace, bool d)
{
	int i =0 ;
	i = (int)type;
	int *c = &tables[i][get_table_index(type, trace, i)];
	if (d == true) {
		if (*c < counter_max) (*c)++;
	} else {
		if ( *c > counter_min && table_update_flag == true)
		{
			(*c)--;
		}
	}
}

int predTable::get_prediction(int type, uint64_t trace) {
	int conf = 0;
	int i =0 ;
	i = (int)type ;
	uint64_t index = get_table_index(type, trace, i);
	conf += tables[i][index];
	return conf;
}

predTable::predTable(int pred_inx_bits, int pred_num_tables)
{
	predictor_tables = pred_num_tables;
	predictor_index_bits = pred_inx_bits;
	predictor_table_entries = ((1 << predictor_index_bits)) ;
	counter_max = (1 << counter_width)-1;
	counter_min = - counter_max;
	tables = new int*[predictor_tables];
	for (int i=0; i < predictor_tables; i++)
	{
		tables[i] = new int[predictor_table_entries];
		memset(tables[i], 0, sizeof(int)*predictor_table_entries);
		for ( int j = 0 ; j < predictor_table_entries; j++){
			tables[i][j] = 0 ;
		}
	}
}

predTable::~predTable()
{
	for(int i = 0; i < predictor_tables; i++)
		delete [] tables[i];
	delete [] tables ;
}

#endif
