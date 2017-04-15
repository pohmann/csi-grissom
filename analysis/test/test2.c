int main(int argc, char** argv){
  int x = atoi(argv[1]);
  int y = atoi(argv[2]);
  if(x < y){
    if(x%2 == 0)
      x++;
    while(x < y){
      x++;
    }
  }
  else
    x--;
  printf("%d %d\n", x, y);
}
