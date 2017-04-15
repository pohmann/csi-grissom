#include <stdio.h>

int counter = 0;

void bar(){
  counter++;
  foo("test");
}

int foo(char* thing){
  if(thing[0] == 'a')
    bar();
  int q = printf(thing);
  return(q + (int)thing[0]);
}

int main(int argc, char** argv){
  if(argc < 4)
    foo(argv[0]);
  else{
    bar();
    foo(argv[4]);
  }
  foo("a print");
  return 15;
}
